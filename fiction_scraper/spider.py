from abc import ABC, abstractmethod
import logging

from lxml.html import document_fromstring, tostring, builder as E
import requests

from . import filters


class Spider(ABC):
    def __init__(self):
        super().__init__()
        self._session = requests.session()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.metadata = {}

    filters = filters.DEFAULT_FILTERS

    @property
    @abstractmethod
    def name(self):
        """The spider name.

        The name or description of the stories this spider crawls.
        """
        return self.__class__.__name__

    @property
    @abstractmethod
    def domain(self):
        """Any URL matching this domain will be crawled with this spider.

        Any leading www. is stripped from the domain before matching.
        """
        pass

    @property
    @abstractmethod
    def url(self):
        """A sample URL of a story that may be scraped with this spider.

        This URL is primarily used in in the usage help text, but a spider
        may also use it internally.
        """
        pass

    @abstractmethod
    def parse(self, url):
        """Parse the specified URL into an iterable of lxml HTML elements.

        If the spider only scrapes a single story, not multiple stories at the
        same domain, it may ignore the specified URL and parse a hardcoded
        URL.

        Typically a spider is implemented as a generator yielding elements.
        During parsing the spider may write metadata to the `self.metadata`
        dict.
        """
        pass

    def fetch(self, url):
        """Fetch a URL and return it as an lxml document.

        Follows HTTP redirects. The `base_url` is set on the returned
        document. All links in the document are converted to absolute links.
        """
        r = self._session.get(url)
        doc = document_fromstring(r.content, base_url=r.url)
        doc.make_links_absolute()
        return doc

    def crawl(self, url, output_file=None):
        """Crawl the specified URL.

        If an output file is specified the serialized HTML output will be
        written to it. The file may be a file-like object or a filename.

        If an output file is not specified, the HTML output will be returned
        as a string.
        """
        # Clear metadata in case story is being re-crawled
        self.metadata = {}

        self.info('beginning parse...')
        body = E.BODY(*self.parse(url))

        self.info('applying filters...')
        for f in self.filters:
            self.debug('running filter %s', self._filter_name(f))
            f(body)

        # parse() must be called before metadata is accessed, or it may not be
        # populated yet.
        head = E.HEAD(*self._generate_meadata_elements())

        doc = E.HTML(head, body)

        if output_file:
            self.info('writing document...')
            return doc.getroottree().write(output_file,
                encoding='UTF-8',
                method='html',
                pretty_print=True,
                doctype='<!doctype html>')

        self.info('tostring on document...')
        return tostring(doc,
            encoding='unicode',
            pretty_print=True,
            doctype='<!doctype html>')

    def debug(self, *args, **kwargs):
        self._logger.debug(*args, **kwargs)

    def info(self, *args, **kwargs):
        self._logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self._logger.warning(*args, **kwargs)

    def critical(self, *args, **kwargs):
        self._logger.critical(*args, **kwargs)

    def log(self, *args, **kwargs):
        self._logger.log(*args, **kwargs)

    def _generate_meadata_elements(self):
        yield E.META(charset="UTF-8")

        for name, content in self.metadata.items():
            if name == 'title':
                yield E.TITLE(content)
            else:
                yield E.META(name=name, content=content)

    @staticmethod
    def _filter_name(type_):
        if not hasattr(type_, '__qualname__'):
            type_ = type(type_)
        return type_.__module__ + '.' + type_.__qualname__
