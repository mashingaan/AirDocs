import sys
from pathlib import Path

# Добавить родительскую директорию в sys.path для импорта core
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from core.version import __version_info__, VERSION

version_tuple = __version_info__ + (0,)

template = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'AirDocs'),
          StringStruct('FileDescription', 'AWB Document Manager'),
          StringStruct('FileVersion', '{VERSION}'),
          StringStruct('ProductName', 'AirDocs'),
          StringStruct('ProductVersion', '{VERSION}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

Path('version_info.txt').write_text(template, encoding='utf-8')
print(f"version_info.txt created for version {VERSION}")
