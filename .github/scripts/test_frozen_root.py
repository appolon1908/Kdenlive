import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_source_scope as scope


class FrozenRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.original)
        subprocess.run(['git', 'init', '-q'], check=True)
        (self.root / 'src').mkdir()
        (self.root / 'src/main.cpp').write_bytes(b'int main() { return 0; }\r\n')
        (self.root / 'build.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.root / 'build.sh').chmod(0o755)
        (self.root / '.github/workflows').mkdir(parents=True)
        (self.root / '.github/workflows/original.yml').write_text('name: original\non: [workflow_dispatch]\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'reviewed root'], check=True)
        self.base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        self.tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip()
        self.repo = 'example/explicit-reviewed-import'

    def manifest(self, tree=None):
        with patch.object(scope, 'FROZEN_ROOT_BASES', {(self.repo, self.base): tree or self.tree}, create=True):
            try:
                return scope.frozen_vendor_manifest(self.base, self.repo, self.base)
            except ValueError as error:
                self.fail(f'exact reviewed root must be supported: {error}')

    def test_explicit_root_pin_derives_every_original_blob_mode(self):
        manifest = self.manifest()
        self.assertEqual(set(manifest['frozen_entries']), {'src/main.cpp', 'build.sh', '.github/workflows/original.yml'})
        self.assertEqual(manifest['frozen_entries']['build.sh']['mode'], '100755')
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD:src/main.cpp'], text=True).strip()
        self.assertEqual(manifest['frozen_entries']['src/main.cpp']['blob'], actual)

    def test_root_pin_does_not_require_fabricated_agents_or_upstream_directory(self):
        manifest = self.manifest()
        self.assertFalse(manifest['application_source_allowed'])
        self.assertEqual(manifest['reviewed_base_tree'], self.tree)

    def test_unregistered_root_is_rejected(self):
        with self.assertRaises(ValueError):
            scope.frozen_vendor_manifest(self.base, self.repo, self.base)

    def test_wrong_registered_root_tree_is_rejected(self):
        with patch.object(scope, 'FROZEN_ROOT_BASES', {(self.repo, self.base): 'f' * 40}, create=True):
            with self.assertRaises(ValueError):
                scope.frozen_vendor_manifest(self.base, self.repo, self.base)

    def test_changed_original_workflow_is_rejected(self):
        manifest = self.manifest()
        entries = dict(manifest['frozen_entries'])
        entries['.github/workflows/original.yml'] = {'mode': '100644', 'blob': 'f' * 40}
        self.assertTrue(scope.validate_frozen_tree(entries, manifest))

    def test_deleted_original_source_is_rejected(self):
        manifest = self.manifest()
        entries = dict(manifest['frozen_entries'])
        del entries['src/main.cpp']
        self.assertTrue(scope.validate_frozen_tree(entries, manifest))
