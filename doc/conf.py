import os

from pkg_resources import parse_version
import pkginfo


# Package info

def _egg_info(path_to_egg='../'):
    path_to_egg = os.path.join(
        os.path.dirname(__file__), path_to_egg)
    egg_info = pkginfo.Develop(path_to_egg)
    release = egg_info.version
    version = '%s.%s' % tuple(map(int, parse_version(release)[0:2]))
    return egg_info.name, egg_info.author, version, release

project, author, version, release = _egg_info()
copyright = '2009, %s' % author


# Extension

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'github.tools.sphinx',
    ]
intersphinx_mapping = {
    'http://docs.python.org/': None,
    }
todo_include_todos = True


# Source

master_doc = 'index'
templates_path = ['_templates']
source_suffix = '.txt'
exclude_trees = []


# Build

html_last_updated_fmt = '%b %d, %Y'
html_static_path = ['_static']
html_style = 'default.css'
html_theme = 'default'

htmlhelp_basename = '%sdoc' % project

latex_documents = [
    ('index',
     '%s.tex' % project,
     u'%s Documentation' % project,
     author,
     'manual',
     )]

pygments_style = 'sphinx'

today_fmt = '%B %d, %Y'
