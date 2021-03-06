from datetime import datetime
from collections import OrderedDict

from pycchdo.log import getLogger


log = getLogger(__name__)


class Sorter(dict):
    def __init__(self, orderby):
        self.orderkeys = self.parse_orderby_to_keys(orderby)
        self.orders = self.orderkeys_to_orders(self.orderkeys)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            return None

    def curr_direction(self, key):
        """The current sort direction for the given key."""
        orderkeys = dict(self.orderkeys)
        if key in orderkeys:
            if orderkeys[key]:
                direction = 'asc'
            else:
                direction = 'desc'
        else:
            direction = None
        return direction

    def parse_orderby_to_keys(self, orderby):
        """Break an orderby string down into tuples of keys and direction.

        e.g. date_start:asc,uid:desc becomes
        [('date_start', False), ('uid', True)]

        """
        raworders = [xxx.split(':') for xxx in orderby.split(',')]
        for order in raworders:
            try:
                if order[1] == 'asc':
                    order[1] = False
                elif order[1] == 'desc':
                    order[1] = True
                else:
                    order[1] = None
            except IndexError:
                order.append(False)
        orders = []
        for key, direction in raworders:
            if direction is None:
                continue
            orders.append((key, direction))
        return orders

    def orderkeys_to_orders(self, raworders):
        orders = []
        for key, direction in raworders:
            keygetter = self[key]
            if keygetter is not None:
                orders.append((keygetter, direction))
        return orders

    def sort(self, lll):
        mmm = lll
        for order, direction in reversed(self.orders):
            mmm = sorted(mmm, key=order, reverse=direction)
        return mmm


class CruiseSorter(Sorter):

    def uid(self, ccc):
        return ccc.uid

    def date_start(self, ccc): 
        dstart = ccc.date_start
        if dstart:
            return dstart
        return datetime(1, 1, 1)

    def aliases(self, ccc):
        aliases = ccc.aliases
        if aliases:
            return aliases[0]
        return ''

    def chiscis(self, ccc):
        chiscis = ccc.chief_scientists
        if chiscis:
            return chiscis[0].person.name
        return ''

    def ship(self, ccc):
        ship = ccc.ship
        if ship:
            return ship.name
        return ''

    def country(self, ccc):
        country = ccc.country
        if country:
            return country.name
        return ''


class SubmissionSorter(Sorter):

    sort_types = OrderedDict([
        ['Submission date', 'submission_date'],
        ['Submitter name', 'submitter_name'],
        ['Line', 'line'],
        ['ExpoCode', 'expocode'],
        ['Ship', 'ship'],
        ['Cruise date', 'date'],
    ])

    def submission_date(self, sub):
        return sub.change.ts_c

    def submitter_name(self, sub):
        person = sub.change.ts_p
        if person:
            return person.name
        return ''

    def line(self, sub):
        return sub.line

    def expocode(self, sub):
        return sub.expocode

    def ship(self, sub):
        return sub.ship_name

    def date(self, sub):
        date = sub.cruise_date
        if date:
            return date
        return datetime(1, 1, 1)


def sort_list(lll, orderby=None):
    """Sort a list of cruises using the orderby criteria."""
    if orderby is None:
        orderby = 'uid'
    sorter = CruiseSorter(orderby)
    return sorter.sort(lll)


def sort_results(results, orderby=None):
    """Sort each category's result cruises using the orderby criteria."""
    if orderby is None:
        orderby = 'uid'
    sorter = CruiseSorter(orderby)
    if results:
        for category, cruises in results.items():
            if isinstance(cruises, list):
                results[category] = sorter.sort(cruises)
            else:
                for obj, ccs in cruises.items():
                    cruises[obj] = sorter.sort(ccs)
    return results

