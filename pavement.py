try:
    import paver
except ImportError:
    # Ignore when not available.
    pass
else:
    from paver.easy import *
    import paver.doctools
    import paver.misctasks


    options(
        cog=Bunch(
            basedir='doc',
            includedir='doc',
            pattern='*.txt',
            beginspec='<==',
            endspec='==>',
            endoutput='<==end==>',
        ),
        sphinx=Bunch(
            docroot='doc',
            builddir='build',
            sourcedir='.',
        ),
    )


    @task
    def clean():
        p = path('doc/build/html/.buildinfo')
        if p.exists():
            p.unlink()


    @task
    def html():
        # Clean out dirs that would be in the way when renaming
        # _sources and _static.
        for dirname in ['sources', 'static']:
            p = path('doc/build/html') / dirname
            if p.exists():
                p.rmtree()
        # Regenerate docs.
        paver.doctools.cog()
        paver.doctools.html()
        paver.doctools.uncog()


    @task
    @needs('html')
    def docs():
        import webbrowser
        index_file = path('doc/build/html/index.html')
        webbrowser.open('file://' + index_file.abspath())


#     @task
#     @needs(['paver.doctools.cog',
#             'paver.doctools.html',
#             'paver.doctools.uncog'])
#     def publish():
#         src_path = path('doc/build/html') / '.'
