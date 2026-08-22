import os
import sys

# Add repo root and eovpn package to Python path for unit testing
# افزودن مسیر پکیج به پایتون جهت اجرای تست‌های خودکار
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
