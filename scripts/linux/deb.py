#!/usr/bin/env python3
import argparse
import datetime
import email.utils
import gzip
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
VERSION_PATTERN = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-z]+\.[0-9]+)?$')
PREFIX = 'usr'
RUNTIME = f'{PREFIX}/lib/ardia'
APPARMOR_SOURCE = 'share/apparmor.d/ardia'
APPARMOR_SHIPPED = f'{PREFIX}/share/ardia/apparmor.d/ardia'
OPTIONAL_LIBRARIES = {'libqt5_shim.so', 'libqt6_shim.so'}
SHARED_LIBRARY = re.compile(r'\.so(\.[0-9]+)*$')
MAINTAINER = 'Ardia <linux@ardia.dev>'
HOMEPAGE = 'https://ardia.dev'
RELEASE_NOTES = 'https://ardia.dev/release-notes'
SOURCE = 'https://github.com/ardia-browser/ardia'

GLIBC_SONAMES = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1', 'ld-linux-x86-64.so.2'}
SONAME_PACKAGES = {
    'libgcc_s.so.1': 'libgcc-s1',
    'libstdc++.so.6': 'libstdc++6',
    'libasound.so.2': 'libasound2t64 | libasound2',
    'libatk-1.0.so.0': 'libatk1.0-0t64 | libatk1.0-0',
    'libatk-bridge-2.0.so.0': 'libatk-bridge2.0-0t64 | libatk-bridge2.0-0',
    'libatspi.so.0': 'libatspi2.0-0t64 | libatspi2.0-0',
    'libcairo.so.2': 'libcairo2',
    'libcups.so.2': 'libcups2t64 | libcups2',
    'libdbus-1.so.3': 'libdbus-1-3',
    'libdrm.so.2': 'libdrm2',
    'libexpat.so.1': 'libexpat1',
    'libgbm.so.1': 'libgbm1',
    'libgio-2.0.so.0': 'libglib2.0-0t64 | libglib2.0-0',
    'libglib-2.0.so.0': 'libglib2.0-0t64 | libglib2.0-0',
    'libgobject-2.0.so.0': 'libglib2.0-0t64 | libglib2.0-0',
    'libnspr4.so': 'libnspr4',
    'libnss3.so': 'libnss3',
    'libnssutil3.so': 'libnss3',
    'libsmime3.so': 'libnss3',
    'libpango-1.0.so.0': 'libpango-1.0-0',
    'libudev.so.1': 'libudev1',
    'libX11.so.6': 'libx11-6',
    'libxcb.so.1': 'libxcb1',
    'libXcomposite.so.1': 'libxcomposite1',
    'libXdamage.so.1': 'libxdamage1',
    'libXext.so.6': 'libxext6',
    'libXfixes.so.3': 'libxfixes3',
    'libxkbcommon.so.0': 'libxkbcommon0',
    'libXrandr.so.2': 'libxrandr2',
}
LOADED_AT_RUNTIME = ['libgtk-3-0t64 | libgtk-3-0', 'polkitd | policykit-1', 'fonts-liberation', 'xdg-utils']
RECOMMENDS = ['libsecret-1-0']

POSTINST = f'''#!/bin/sh
set -e
if [ "$1" = configure ] && [ -e /etc/apparmor.d/abi/4.0 ]; then
  install -m 0644 /{APPARMOR_SHIPPED} /etc/apparmor.d/ardia
  if command -v apparmor_parser >/dev/null 2>&1 && [ "$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null)" = Y ]; then
    apparmor_parser -r -T -W /etc/apparmor.d/ardia 2>/dev/null \\
      || echo "ardia: could not load /etc/apparmor.d/ardia; it loads at the next boot" >&2
  fi
fi
'''

POSTRM = '''#!/bin/sh
set -e
case "$1" in
  remove|purge)
    if [ -e /etc/apparmor.d/ardia ]; then
      if command -v apparmor_parser >/dev/null 2>&1 && [ -d /sys/kernel/security/apparmor ]; then
        apparmor_parser -R /etc/apparmor.d/ardia >/dev/null 2>&1 || true
      fi
      rm -f /etc/apparmor.d/ardia
    fi
    rm -f /var/cache/apparmor/*/ardia
    ;;
esac
'''


class DebError(Exception):
    pass


def debian_version(version):
    if not VERSION_PATTERN.fullmatch(version):
        raise DebError(f'bad version {version!r}: expected <major>.<minor>.<patch> or <major>.<minor>.<patch>-<channel>.<n>')
    return version.replace('-', '~')


def deb_name(version):
    return f'ardia_{version}_amd64.deb'


def is_elf(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open('rb') as handle:
        return handle.read(4) == b'\x7fELF'


def readelf(*args):
    result = subprocess.run(['readelf', *args], capture_output=True, text=True, env={**os.environ, 'LC_ALL': 'C', 'LANGUAGE': ''})
    if result.returncode != 0:
        raise DebError(f'readelf {" ".join(args)} failed: {result.stderr.strip()}')
    return result.stdout


def needed_libraries(path):
    return re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', readelf('-d', '--wide', str(path)))


def glibc_versions(path):
    return set(re.findall(r'\bGLIBC_([0-9]+(?:\.[0-9]+)+)\b', readelf('-V', '--wide', str(path))))


def version_key(version):
    return tuple(int(part) for part in version.split('.'))


def depends(runtime):
    bundled = {path.name for path in runtime.rglob('*') if path.is_file() or path.is_symlink()}
    sonames = set()
    glibc = {'2.17'}
    for path in sorted(runtime.rglob('*')):
        if path.name in OPTIONAL_LIBRARIES or not is_elf(path):
            continue
        needed = needed_libraries(path)
        if path.name == 'chrome' and not needed:
            raise DebError(f'readelf found no libraries that {path} needs')
        sonames.update(needed)
        glibc |= glibc_versions(path)
    unknown = sorted(name for name in sonames - bundled - GLIBC_SONAMES if name not in SONAME_PACKAGES)
    if unknown:
        raise DebError('no Debian package known for ' + ', '.join(unknown) + ': add it to SONAME_PACKAGES in scripts/linux/deb.py')
    packages = [f'libc6 (>= {max(glibc, key=version_key)})']
    for name in sorted(sonames - bundled - GLIBC_SONAMES):
        if SONAME_PACKAGES[name] not in packages:
            packages.append(SONAME_PACKAGES[name])
    return packages + [package for package in LOADED_AT_RUNTIME if package not in packages]


def extract(tarball, destination):
    try:
        with tarfile.open(tarball) as packed:
            packed.extractall(destination, filter='data')
    except (tarfile.TarError, OSError, EOFError) as error:
        raise DebError(f'could not extract {tarball}: {error}') from None
    root = destination / 'ardia'
    for required in ('install.sh', 'lib/ardia/chrome', APPARMOR_SOURCE):
        if not (root / required).exists():
            raise DebError(f'{tarball.name} is not an Ardia release package: no ardia/{required}')
    return root


def runs_directly(path):
    with path.open('rb') as handle:
        magic = handle.read(4)
    if magic[:2] == b'#!':
        return True
    return magic == b'\x7fELF' and not SHARED_LIBRARY.search(path.name)


def normalize_modes(stage):
    for path in [stage, *stage.rglob('*')]:
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.stat().st_mode & 0o111 and not runs_directly(path):
            path.chmod(0o644)


def installed_size(stage):
    total = 0
    for path in stage.rglob('*'):
        if path.relative_to(stage).parts[0] == 'DEBIAN':
            continue
        total += 1 if path.is_symlink() or path.is_dir() else -(-path.stat().st_size // 1024)
    return total


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def write_docs(stage, version, date):
    docs = stage / f'{PREFIX}/share/doc/ardia'
    write(docs / 'copyright', f'''Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Ardia
Source: {SOURCE}

Files: *
Copyright: 2026 Mantra Patel
License: GPL-3
 Ardia as distributed, with its Chromium engine built with Helium's patches, is
 licensed under the GNU General Public License, version 3. Ardia's own source
 files are also available under the Apache License, Version 2.0, and the
 engine includes Chromium (BSD-3-Clause and others, see chrome://credits),
 Helium (GPL-3.0) and uBlock Origin (GPL-3.0). Corresponding Source: the
 repository at the v{version} tag of {SOURCE}.
 .
 On Debian systems, the full text of the GNU General Public License version 3
 can be found in /usr/share/common-licenses/GPL-3.
''')
    changelog = f'''ardia ({debian_version(version)}) stable; urgency=medium

  * Ardia {version}: {RELEASE_NOTES}#{version}

 -- {MAINTAINER}  {email.utils.format_datetime(date)}
'''
    with (docs / 'changelog.gz').open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=9, mtime=int(date.timestamp())) as packed:
            packed.write(changelog.encode())
    (docs / 'changelog.gz').chmod(0o644)


def md5sums(stage):
    lines = []
    for path in sorted(stage.rglob('*')):
        relative = path.relative_to(stage)
        if relative.parts[0] == 'DEBIAN' or path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, lambda: hashlib.md5(usedforsecurity=False)).hexdigest()
        lines.append(f'{digest}  {relative.as_posix()}\n')
    return ''.join(lines)


def build(tarball, destination, version=None, maintainer=MAINTAINER):
    if destination.exists():
        raise DebError(f'refusing to overwrite {destination}')
    if shutil.which('dpkg-deb') is None:
        raise DebError('dpkg-deb is required (apt install dpkg, pacman -S dpkg)')
    with tempfile.TemporaryDirectory(prefix='ardia-deb-') as scratch:
        scratch = pathlib.Path(scratch)
        source = extract(tarball, scratch / 'src')
        packaged = (source / 'lib/ardia/VERSION').read_text().strip() if (source / 'lib/ardia/VERSION').is_file() else None
        if version is None:
            if packaged is None:
                raise DebError(f'{tarball.name} has no lib/ardia/VERSION: pass --version')
            version = packaged
        elif packaged is not None and packaged != version:
            raise DebError(f'{tarball.name} is Ardia {packaged}, not {version}')
        control_version = debian_version(version)
        stage = scratch / 'stage'
        stage.mkdir(mode=0o755)
        os.chmod(stage, 0o755)
        result = subprocess.run(['bash', str(source / 'install.sh'), '--prefix', f'/{PREFIX}', '--destdir', str(stage)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise DebError(f'install.sh --destdir failed: {result.stderr.strip()}')
        apparmor = stage / APPARMOR_SHIPPED
        apparmor.parent.mkdir(parents=True)
        shutil.copyfile(source / APPARMOR_SOURCE, apparmor)
        apparmor.chmod(0o644)
        epoch = int(os.environ.get('SOURCE_DATE_EPOCH') or tarball.stat().st_mtime)
        date = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
        write_docs(stage, version, date)
        normalize_modes(stage)
        control = stage / 'DEBIAN'
        control.mkdir(mode=0o755)
        fields = [
            ('Package', 'ardia'),
            ('Version', control_version),
            ('Architecture', 'amd64'),
            ('Maintainer', maintainer),
            ('Installed-Size', str(installed_size(stage))),
            ('Depends', ', '.join(depends(stage / RUNTIME))),
            ('Recommends', ', '.join(RECOMMENDS)),
            ('Provides', 'www-browser'),
            ('Section', 'web'),
            ('Priority', 'optional'),
            ('Homepage', HOMEPAGE),
            ('Description', "Chromium-based browser with Arc's sidebar and Dia's polish\n"
             " Ardia is a web browser built on Chromium, with its tabs in a sidebar.\n"
             " It needs no account."),
        ]
        write(control / 'control', ''.join(f'{name}: {value}\n' for name, value in fields))
        write(control / 'md5sums', md5sums(stage))
        write(control / 'postinst', POSTINST, 0o755)
        write(control / 'postrm', POSTRM, 0o755)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name('.' + destination.name + '.partial')
        partial.unlink(missing_ok=True)
        result = subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z6', '--build', str(stage), str(partial)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            partial.unlink(missing_ok=True)
            raise DebError(f'dpkg-deb --build failed: {result.stderr.strip()}')
        os.replace(partial, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description='Builds ardia_<version>_amd64.deb from an Ardia Linux release tarball.')
    parser.add_argument('--package', type=pathlib.Path, required=True, help='Ardia-<version>-linux-x64.tar.xz')
    parser.add_argument('--destination', type=pathlib.Path, help='the .deb to write (default ardia_<version>_amd64.deb beside the tarball)')
    parser.add_argument('--version', help="the Ardia version (default: the tarball's lib/ardia/VERSION, which it must match)")
    parser.add_argument('--maintainer', default=os.environ.get('ARDIA_DEB_MAINTAINER', MAINTAINER), help=f'the Maintainer field (default $ARDIA_DEB_MAINTAINER or {MAINTAINER})')
    args = parser.parse_args()
    try:
        tarball = args.package.resolve()
        version = args.version
        if version is None:
            match = re.fullmatch(r'Ardia-(.+)-linux-x64\.tar\.xz', tarball.name)
            version = match.group(1) if match and VERSION_PATTERN.fullmatch(match.group(1)) else None
        destination = args.destination
        if destination is None:
            if version is None:
                parser.error('pass --destination or --version for a tarball not named Ardia-<version>-linux-x64.tar.xz')
            destination = tarball.with_name(deb_name(version))
        print(build(tarball, destination.resolve(), version, args.maintainer))
    except (DebError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
