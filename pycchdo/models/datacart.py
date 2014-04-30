from libcchdo.recipes.orderedset import OrderedSet

from pycchdo.models.serial import Change


class Datacart(OrderedSet):
    """A Datacart contains files that are meant to be downloaded in bulk.

    Each file is refered to by attribute id.

    """
    def files(self):
        print repr(list(self))
        return Change.get_all_by_ids(list(self))

    @classmethod
    def is_file_type_allowed(cls, ftype):
        """Determine whether a data file of ftype is allowed in the data cart.

        """
        prefixes = ['btl', 'bot', 'ctd', 'doc', 'sum']
        for prefix in prefixes:
            if ftype.startswith(prefix):
                return True
        return False

    def cruise_files_in_cart(self, cruise):
        """Return a tuple of the number of files in cart and number of files.

        """
        file_attrs = cruise.file_attrs

        file_count = 0
        for ftype, fattr in file_attrs.items():
            if not self.is_file_type_allowed(ftype):
                continue
            if fattr.id in self:
                file_count += 1
        return (file_count, len(file_attrs))
