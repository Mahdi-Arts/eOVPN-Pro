project(
  'eovpn',
  version: '1.5.0',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.60.0',
  default_options: ['warning_level=2', 'c_std=gnu11'],
)

# Build/runtime discovery / شناسایی وابستگی‌های ساخت و اجرا
i18n = import('i18n')
python = import('python')
python_installation = python.find_installation('python3', required: true)
if not python_installation.language_version().version_compare('>= 3.10')
  error('eOVPN-Pro requires Python 3.10 or newer')
endif

dependency('gtk4', version: '>= 4.6')
dependency('libadwaita-1', version: '>= 1.1')
dependency('libsecret-1', version: '>= 0.20')
dependency('libnotify', version: '>= 0.7')

gnome = import('gnome')
project_id = 'io.github.Mahdi_Arts.eOVPN_Pro'

prefix = get_option('prefix')
bindir = get_option('bindir')
datadir = get_option('datadir')
pkg_datadir = prefix / datadir / meson.project_name()
schemas_dir = prefix / datadir / 'glib-2.0' / 'schemas'
icondir = prefix / datadir / 'icons' / 'hicolor'
# Native CFFI modules require the architecture-specific Python directory.
# ماژول‌های بومی CFFI باید در مسیر وابسته به معماری پایتون نصب شوند.
python_dir = python_installation.get_install_dir(pure: false)

conf = configuration_data()
conf.set('PACKAGE_URL', 'https://github.com/Mahdi-Arts/eOVPN-Pro')
conf.set('DATA_DIR', datadir)
conf.set('PKG_DATADIR', pkg_datadir)
conf.set('LOCALE_DIR', prefix / get_option('localedir'))
conf.set('PYTHON_DIR', python_dir)

launcher = configure_file(
  input: 'eovpn.in',
  output: 'eovpn.py',
  configuration: conf,
)
install_data(
  launcher,
  install_dir: bindir,
  rename: 'eovpn',
  install_mode: 'rwxr-xr-x',
)

subdir('eovpn')
subdir('po')
subdir('data')
subproject('networkmanager')
if get_option('openvpn3')
  subproject('openvpn3')
endif

# Python package sources / سورس‌های پکیج پایتون
install_subdir(
  'eovpn',
  install_dir: python_dir,
  exclude_directories: ['__pycache__'],
)

# Offline unit suite integrated with Meson / اتصال تست‌های آفلاین به Meson
unit_tests = find_program('python3')
test(
  'python-unit-tests',
  unit_tests,
  args: ['-m', 'unittest', 'discover', '-s', meson.project_source_root() / 'tests', '-v'],
  workdir: meson.project_source_root(),
  timeout: 120,
)

meson.add_install_script('meson_post_install.py')
