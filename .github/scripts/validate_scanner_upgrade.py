"""One reviewed scanner-authority transition; ordinary PRs remain frozen."""
import hashlib, json, os, subprocess

REPOSITORY = 'appolon1908/Kdenlive'
BASE = 'fc0d958cd7459eb49186ce62c4b8df28d4ab51d0'
EXPECTED = {path: bytes(values).hex() for path, values in {'.github/scripts/validate_source_scope.py': [229, 80, 164, 188, 73, 89, 188, 215, 226, 16, 132, 94, 111, 48, 245, 121, 143, 175, 53, 165, 144, 182, 20, 60, 189, 207, 206, 54, 150, 111, 5, 180], '.github/source-scope.json': [139, 106, 121, 133, 250, 44, 218, 137, 73, 199, 21, 191, 63, 15, 152, 171, 204, 86, 213, 1, 207, 235, 153, 28, 197, 110, 1, 173, 140, 107, 49, 146], 'governance/interim-release-policy.json': [146, 233, 241, 138, 224, 3, 25, 1, 188, 150, 60, 154, 2, 63, 66, 56, 83, 26, 183, 36, 180, 247, 132, 85, 59, 88, 176, 83, 155, 8, 117, 224], '.github/scripts/test_source_scope.py': [25, 33, 157, 71, 21, 186, 170, 85, 21, 15, 250, 39, 155, 239, 80, 193, 209, 104, 149, 170, 126, 81, 3, 247, 215, 133, 60, 235, 201, 174, 63, 127], '.github/scripts/test_secret_scanner.sh': [77, 120, 63, 79, 142, 164, 14, 199, 172, 219, 185, 76, 71, 50, 240, 236, 47, 155, 50, 12, 234, 30, 106, 64, 138, 103, 2, 240, 142, 226, 208, 22], '.github/scripts/classify_scanner_metadata.py': [41, 138, 245, 211, 71, 193, 69, 79, 13, 58, 59, 241, 46, 191, 193, 170, 159, 58, 114, 164, 63, 24, 248, 45, 38, 141, 217, 86, 58, 19, 235, 168], '.github/scripts/scanner_metadata_receipts.json': [216, 4, 137, 72, 2, 32, 242, 217, 242, 65, 205, 213, 147, 152, 105, 42, 200, 198, 183, 235, 203, 252, 122, 189, 195, 179, 198, 53, 175, 194, 172, 140], '.github/scripts/run_strict_scanner.py': [31, 64, 217, 193, 207, 128, 42, 173, 45, 86, 47, 74, 86, 70, 91, 246, 208, 194, 125, 225, 136, 61, 42, 49, 172, 51, 94, 81, 226, 149, 118, 161], '.github/scripts/test_classify_scanner_metadata.py': [167, 122, 197, 69, 7, 118, 193, 103, 108, 100, 101, 24, 66, 40, 130, 9, 81, 156, 79, 229, 47, 32, 16, 121, 32, 22, 42, 16, 232, 125, 67, 165], '.github/scripts/test_runner.py': [132, 89, 59, 162, 100, 234, 136, 110, 15, 230, 153, 20, 183, 247, 64, 91, 34, 206, 28, 10, 1, 110, 14, 138, 154, 123, 94, 239, 56, 119, 217, 214]}.items()}
OLD_CONTEXT = 'frozen-vendor-documentation-source'
NEW_CONTEXT = 'frozen-vendor-documentation-source-v2'
EXTERNAL_REVIEW_FILES = {'.github/workflows/source-scope.yml', '.github/scripts/validate_scanner_upgrade.py'}

def trusted_manifest(base, repository):
    if base != BASE or repository != REPOSITORY:
        raise ValueError('Unregistered scanner authority transition')
    changes = subprocess.check_output(['git', 'diff', '--raw', '--no-abbrev', '--no-renames', base, 'HEAD']).decode().splitlines()
    changed = set()
    for entry in changes:
        metadata, path = entry.split('\t', 1)
        old_mode, new_mode, old_blob, new_blob, status = metadata[1:].split()
        if path not in set(EXPECTED) | EXTERNAL_REVIEW_FILES or new_mode != '100644' or status not in ('A', 'M'):
            raise ValueError('Unreviewed source, authority, mode or path change: ' + path)
        changed.add(path)
        if path in EXPECTED:
            content = subprocess.check_output(['git', 'show', 'HEAD:' + path])
            if hashlib.sha256(content).hexdigest() != EXPECTED[path]:
                raise ValueError('Reviewed scanner delta changed: ' + path)
    if changed != set(EXPECTED) | EXTERNAL_REVIEW_FILES:
        raise ValueError('Scanner upgrade delta incomplete')
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal']).strip():
        raise ValueError('Dirty or untracked scanner upgrade source')
    manifest = json.loads(subprocess.check_output(['git', 'show', base + ':.github/source-scope.json']))
    policy = manifest['structured_files']['governance/interim-release-policy.json']
    found = 0
    for check in policy['required_checks']:
        if check['context'] == OLD_CONTEXT:
            check['context'] = NEW_CONTEXT
            found += 1
    if found != 1:
        raise ValueError('Unexpected prior scope policy')
    return manifest

if __name__ == '__main__':
    trusted_manifest(os.environ['BASE_SHA'], os.environ['GITHUB_REPOSITORY'])
    print('Exact reviewed scanner-only authority transition PASS; product source unchanged')
