from tempfile import NamedTemporaryFile

from docutils.readers.doctree import Reader
from docutils.io import StringInput, NullOutput, DocTreeInput, StringOutput
from docutils.core import Publisher

import locale
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass


pub_in = Publisher(source_class=StringInput, destination_class=NullOutput)
pub_in.set_components('standalone', 'restructuredtext', 'null')
pub_in.process_programmatic_settings(None, None, None)


pub_out = Publisher(
    reader = Reader(parser_name='null'), destination_class=StringOutput)
pub_out.set_writer('html')


def reST_to_html_div(source, prefix='history-', class_='history-note'):
    """Publish a reST document to a unicode HTML snippet enclosed in a div.

    """
    pub_in.settings.id_prefix = prefix
    pub_in.settings.report_level = 'quiet'
    pub_in.set_source(source, None)
    pub_in.set_io()
    pub_in.document = pub_in.reader.read(
        pub_in.source, pub_in.parser, pub_in.settings)
    pub_in.apply_transforms()
    document = pub_in.document
    pub_out.source = DocTreeInput(document)
    pub_out.process_programmatic_settings(None, None, None)

    try:
        docid = document['ids'][0]
    except IndexError:
        docid = 'doc'

    with NamedTemporaryFile() as template:
        template.write("""\
<div id="{0}" class="{1} rendered">
%(body_pre_docinfo)s
%(docinfo)s
%(body)s
</div>""".format(docid, class_))
        template.flush()

        pub_out.settings.template = template.name
        pub_out.settings.table_style = 'borderless'
        pub_out.settings.report_level = 'quiet'
        return unicode(pub_out.publish(enable_exit_status=False), 'utf8')
