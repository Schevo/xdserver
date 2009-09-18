try:
    import paver
except ImportError:
    # Ignore when not available.
    pass
else:
    from paver.easy import *
    import paver.misctasks


    options(
        cog=Bunch(
            basdir='doc/src',
            includedir='doc/src',
            pattern='*.txt',
            beginspec='<==',
            endspec='==>',
            endoutput='<==end==>',
        ),
        sphinx=Bunch(
            docroot='doc',
            builddir='build',
            sourcedir='src',
        ),
    )


    @task
    @needs(['paver.doctools.cog',
            'paver.doctools.html',
            'paver.doctools.uncog'])
    def html():
        pass


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
