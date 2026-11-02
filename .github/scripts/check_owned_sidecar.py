"""Isolated owned-sidecar checks; no renderer, systemd or provider is executed."""
import configparser
import http.client
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml

REPO = Path.cwd()

class OwnedSidecarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with patch.dict(os.environ, {'CODESTRA_VIDEO_ROOT': str(self.root), 'CODESTRA_VIDEO_API_TOKEN': 'fixture-token', 'CODESTRA_VIDEO_RENDER_ENABLED': '0'}):
            spec = importlib.util.spec_from_file_location('reviewed_sidecar', REPO / 'codestra_api/server.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def request(self, method, path, body=None, authorization='Bearer fixture-token'):
        server = self.module.ThreadingHTTPServer(('127.0.0.1', 0), self.module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(self.module.subprocess, 'Popen', side_effect=AssertionError('renderer forbidden')):
                client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                headers = {'Content-Type': 'application/json'}
                if authorization is not None:
                    headers['Authorization'] = authorization
                client.request(method, path, body=body, headers=headers)
                response = client.getresponse()
                result = response.status, json.loads(response.read())
                client.close()
                return result
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_authentication_denies_missing_wrong_and_non_bearer_credentials(self):
        for credential in (None, 'Bearer incorrect', 'Basic fixture-token'):
            for method, path in (('GET', '/health'), ('GET', '/status'), ('POST', '/render')):
                with self.subTest(credential=credential, method=method, path=path):
                    self.assertEqual(self.request(method, path, '{}', credential), (401, {'error': 'unauthorized'}))
        self.assertEqual(self.module._jobs, {})

    def test_authenticated_health_only_returns_readback(self):
        status, result = self.request('GET', '/health')
        self.assertEqual(status, 200)
        self.assertEqual(result['service'], 'codestra-mlt-api')
        self.assertFalse(result['render_enabled'])
        self.assertEqual(self.module._jobs, {})

    def test_disabled_render_cannot_create_jobs_or_execute(self):
        self.assertEqual(self.request('POST', '/render', '{}'), (403, {'error': 'render_disabled'}))
        self.assertEqual(self.module._jobs, {})

    def test_unknown_jobs_and_routes_are_not_found(self):
        for method, path, error in [('GET', '/status/missing', 'job_not_found'), ('POST', '/stop/missing', 'job_not_found'), ('GET', '/unknown', 'not_found')]:
            self.assertEqual(self.request(method, path, '{}'), (404, {'error': error}))

    def test_read_json_rejects_array_malformed_and_oversized_payloads(self):
        for body, error in [('[]', 'json_object_required'), ('x' * (1024 * 1024 + 1), 'payload_too_large'), ('{', None)]:
            handler = object.__new__(self.module.Handler)
            handler.headers = {'Content-Length': str(len(body))}
            handler.rfile = io.BytesIO(body.encode())
            with self.subTest(error=error), self.assertRaises(ValueError):
                handler.read_json()

    def test_paths_reject_absolute_parent_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'outside').symlink_to(outside, target_is_directory=True)
            for value in ('/etc/passwd', '../escape', 'outside/file'):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'path_outside_video_root'):
                    self.module.safe_path(value)
        self.assertEqual(self.module.safe_path('outputs/result.mp4'), self.root / 'outputs/result.mp4')

    def test_mlt_arguments_are_separate_and_confined(self):
        project = self.root / 'project with spaces.mlt'
        project.write_text('<mlt/>')
        result = self.module.command_for({'project': project.name, 'output': 'output/result.mp4', 'profile': 'hdv_720_25p', 'vcodec': 'libx264', 'crf': 20})
        self.assertEqual(result, ['melt', '-profile', 'hdv_720_25p', str(project), '-consumer', f'avformat:{self.root / "output/result.mp4"}', 'vcodec=libx264', 'crf=20'])

    def test_mlt_rejects_shell_and_path_injection_in_options(self):
        (self.root / 'project.mlt').write_text('<mlt/>')
        for key in ('profile', 'vcodec', 'acodec', 'format', 'preset', 'crf'):
            for value in ('x;touch forbidden', '$(id)', '../../escape'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.module.command_for({'project': 'project.mlt', 'output': 'output/result.mp4', key: value})

    def test_missing_engine_cannot_execute(self):
        self.module.RENDER_ENABLED = True
        with patch.object(self.module.shutil, 'which', return_value=None), patch.object(self.module.subprocess, 'Popen', side_effect=AssertionError('must not run')):
            with self.assertRaisesRegex(FileNotFoundError, 'engine_binary_missing'):
                self.module.launch({})
        self.assertEqual(self.module._jobs, {})

    def test_capacity_guard_cannot_execute(self):
        self.module.RENDER_ENABLED = True
        self.module._jobs['occupied'] = {'state': 'running'}
        with patch.object(self.module.shutil, 'which', return_value='/not-executed/melt'), patch.object(self.module.subprocess, 'Popen', side_effect=AssertionError('must not run')):
            with self.assertRaisesRegex(RuntimeError, 'job_capacity_reached'):
                self.module.launch({})

    def test_entrypoint_refuses_missing_credential_and_public_bind(self):
        for arguments, message in [([], 'CODESTRA_VIDEO_API_TOKEN_required'), (['--host', '0.0.0.0'], 'refusing_non_loopback_bind')]:
            env = {**os.environ, 'CODESTRA_VIDEO_ROOT': str(self.root), 'CODESTRA_VIDEO_API_TOKEN': '', 'CODESTRA_VIDEO_RENDER_ENABLED': '0'}
            result = subprocess.run(['python3', str(REPO / 'codestra_api/server.py'), *arguments], env=env, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_original_self_test_only_uses_temporary_source_state(self):
        env = {**os.environ, 'CODESTRA_VIDEO_ROOT': str(self.root), 'CODESTRA_VIDEO_API_TOKEN': '', 'CODESTRA_VIDEO_RENDER_ENABLED': '0'}
        result = subprocess.run(['python3', str(REPO / 'codestra_api/server.py'), '--self-test'], env=env, capture_output=True, text=True, check=True, timeout=5)
        self.assertEqual(json.loads(result.stdout), {'ok': True, 'engine': 'mlt', 'service': 'codestra-mlt-api'})

    def test_systemd_preserves_private_unprivileged_scope(self):
        unit = configparser.ConfigParser(interpolation=None, strict=False)
        unit.read(REPO / 'codestra_api/systemd/codestra-mlt-api.service')
        service = unit['Service']
        self.assertEqual(service['User'], 'videoctl')
        self.assertEqual(service['Group'], 'videoctl')
        self.assertIn('--host 127.0.0.1 --port 18102', service['ExecStart'])
        for key in ('NoNewPrivileges', 'PrivateTmp', 'ProtectHome'):
            self.assertEqual(service[key], 'true')
        self.assertEqual(service['ProtectSystem'], 'strict')
        self.assertEqual(service['EnvironmentFile'], '/etc/codestra-video/mlt.env')
        self.assertEqual(set(service['ReadWritePaths'].split()), {'/srv/codestra-video', '/var/lib/codestra-video'})

    def test_openapi_only_declares_owned_loopback_routes(self):
        contract = yaml.safe_load((REPO / 'codestra_api/openapi.yaml').read_text())
        self.assertEqual(contract['servers'], [{'url': 'http://127.0.0.1:18102'}])
        self.assertEqual(set(contract['paths']), {'/health', '/status', '/status/{job_id}', '/render', '/stop/{job_id}'})
        self.assertEqual(set(contract['paths']['/render']), {'post'})
        self.assertEqual(set(contract['paths']['/health']), {'get'})

if __name__ == '__main__':
    unittest.main()
