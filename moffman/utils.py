"""
.. module: moffman.utils
   :synopsis: Helper classes and functions.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import os.path


FILENAME_SANITIZATION_MAP = {
    ".": "-",
    "/": "-"
}


class MoffmanError(Exception):
    pass


def sanitize_filename(file_name):
    name, ext = os.path.splitext(file_name)
    for c, replacement in FILENAME_SANITIZATION_MAP.items():
        name = name.replace(c, replacement)

    return name + ext
