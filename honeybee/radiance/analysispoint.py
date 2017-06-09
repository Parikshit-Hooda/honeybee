"""Honeybee PointGroup and TestPointGroup."""
from __future__ import division
from ..vectormath.euclid import Point3, Vector3
from ..dataoperation import matchData

import os
from collections import defaultdict
from itertools import izip
import types
import copy


class AnalysisPoint(object):
    """A radiance analysis point.

    Attributes:
        location: Location of analysis points as (x, y, z).
        direction: Direction of analysis point as (x, y, z).

    This class is developed to enable honeybee for running daylight control
    studies with dynamic shadings without going back to several files.
    """

    __slots__ = ('_loc', '_dir', '_sources', '_values', '_isDirectLoaded', 'logic')

    def __init__(self, location, direction):
        """Create an analysis point."""
        self.location = location
        self.direction = direction
        # name of sources and their state. It's only meaningful in multi-phase daylight
        # analysis. In analysis for a single time it will be {None: [None]}
        self._sources = {}

        # an empty list for values
        # for each source there will be a new list
        # inside each source list there will be a dictionary for each state
        # in each dictionary the key is the hoy and the values are a list which
        # is [total, direct]. If the value is not available it will be None
        self._values = []
        self._isDirectLoaded = False
        self.logic = self._logic

    @classmethod
    def fromrawValues(cls, x, y, z, x1, y1, z1):
        """Create an analysi point from 6 values.

        x, y, z are the location of the point and x1, y1 and z1 is the direction.
        """
        return cls((x, y, z), (x1, y1, z1))

    @property
    def location(self):
        """Location of analysis points as Point3."""
        return self._loc

    @location.setter
    def location(self, location):
        try:
            self._loc = Point3(*(float(l) for l in location))
        except TypeError:
            raise TypeError(
                'Failed to convert {} to location.\n'
                'location should be a list or a tuple with 3 values.'.format(location))

    @property
    def direction(self):
        """Direction of analysis points as Point3."""
        return self._dir

    @direction.setter
    def direction(self, direction):
        try:
            self._dir = Vector3(*(float(d) for d in direction))
        except TypeError:
            raise TypeError(
                'Failed to convert {} to direction.\n'
                'location should be a list or a tuple with 3 values.'.format(direction))

    @property
    def sources(self):
        """Get sorted list fo sources."""
        srcs = range(len(self._sources))
        for name, d in self._sources.iteritems():
            srcs[d['id']] = name
        return srcs

    @property
    def details(self):
        """Human readable details."""
        header = 'Location: {}\nDirection: {}\n#hours: {}\n#window groups: {}\n'.format(
            ', '.join(str(c) for c in self.location),
            ', '.join(str(c) for c in self.direction),
            len(self.hoys), len(self._sources)
        )
        sep = '-' * 15
        wg = '\nWindow Group {}: {}\n'
        st = '....State {}: {}\n'

        # sort sources based on ids
        sources = range(len(self._sources))
        for s, d in self._sources.iteritems():
            sources[d['id']] = (s, d)

        # create the string for eacj window groups
        notes = [header, sep]
        for count, s in enumerate(sources):
            name, states = s
            notes.append(wg.format(count, name))
            for count, name in enumerate(states['state']):
                notes.append(st.format(count, name))

        return ''.join(notes)

    @property
    def hasValues(self):
        """Check if this point has results values."""
        return len(self._values) != 0

    @property
    def hasDirectValues(self):
        """Check if direct values are loaded for this point.

        In some cases and based on the recipe only total values are available.
        """
        return self._isDirectLoaded

    @property
    def hoys(self):
        """Return hours of the year for results if any."""
        if not self.hasValues:
            return []
        else:
            return sorted(self._values[0][0].keys())

    @staticmethod
    def _logic(*args, **kwargs):
        """Dynamic blinds state logic.

        If the logic is not met the blind will be moved to the next state.
        Overwrite this method for optional blind control.
        """
        return args[0] > 2000

    def sourceId(self, source):
        """Get source id if available."""
        # find the id for source and state
        try:
            return self._sources[source]['id']
        except KeyError:
            raise ValueError('Invalid source input: {}'.format(source))

    def blindStateId(self, source, state):
        """Get state id if available."""
        if str(state).isdigit():
            return int(state)
        try:
            return self._sources[source]['state'].index(state)
        except ValueError:
            raise ValueError('Invalid state input: {}'.format(state))

    @property
    def states(self):
        """Get list of states names for each source."""
        return tuple(s[1]['state'] for s in self._sources.iteritems())

    @property
    def longestStateIds(self):
        """Get longest combination between blind states as blindsStateIds."""
        states = tuple(len(s[1]['state']) - 1 for s in self._sources.iteritems())

        return tuple(tuple(min(s, i) for s in states)
                     for i in range(max(states) + 1))

    def _createDataStructure(self, source, state):
        """Create place holders for sources and states if needed.

        Returns:
            source id and state id as a tuple.
        """
        def double():
            return [None, None]

        currentSources = self._sources.keys()
        if source not in currentSources:
            self._sources[source] = {
                'id': len(currentSources),
                'state': []
            }

            # append a new list to values for the new source
            self._values.append([])

        # find the id for source and state
        sid = self._sources[source]['id']

        if state not in self._sources[source]['state']:
            # add sources
            self._sources[source]['state'].append(state)
            # append a new dictionary for this state
            self._values[sid].append(defaultdict(double))

        # find the state id
        stateid = self._sources[source]['state'].index(state)

        return sid, stateid

    def setValue(self, value, hoy, source=None, state=None, isDirect=False):
        """Set value for a specific hour of the year.

        Args:
            value: Illuminance value as a number.
            hoy: The hour of the year that corresponds to this value.
            source: Name of the source of light. Only needed in case of multiple
                sources / window groups (default: None).
            state: State of the source if any (default: None).
            isDirect: Set to True if the value is direct contribution of sunlight.
        """
        sid, stateid = self._createDataStructure(source, state)
        if isDirect:
            self._isDirectLoaded = True
        ind = 1 if isDirect else 0
        self._values[sid][stateid][hoy][ind] = value

    def setValues(self, values, hoys, source=None, state=None, isDirect=False):
        """Set values for several hours of the year.

        Args:
            values: List of Illuminance values as numbers.
            hoys: List of hours of the year that corresponds to input values.
            source: Name of the source of light. Only needed in case of multiple
                sources / window groups (default: None).
            state: State of the source if any (default: None).
            isDirect: Set to True if the value is direct contribution of sunlight.
        """
        if not (isinstance(values, types.GeneratorType) or
                isinstance(hoys, types.GeneratorType)):

            assert len(values) == len(hoys), \
                ValueError(
                    'Length of values [%d] is not equal to length of hoys [%d].'
                    % (len(values), len(hoys)))

        sid, stateid = self._createDataStructure(source, state)

        if isDirect:
            self._isDirectLoaded = True

        ind = 1 if isDirect else 0
        for hoy, value in izip(hoys, values):
            self._values[sid][stateid][hoy][ind] = value

    def setCoupledValue(self, value, hoy, source=None, state=None):
        """Set both total and direct values for a specific hour of the year.

        Args:
            value: Illuminance value as as tuples (total, direct).
            hoy: The hour of the year that corresponds to this value.
            source: Name of the source of light. Only needed in case of multiple
                sources / window groups (default: None).
            state: State of the source if any (default: None).
        """
        sid, stateid = self._createDataStructure(source, state)

        try:
            self._values[sid][stateid][hoy] = value[0], value[1]
        except TypeError:
            raise ValueError(
                "Wrong input: {}. Input values must be of length of 2.".format(value)
            )
        except IndexError:
            raise ValueError(
                "Wrong input: {}. Input values must be of length of 2.".format(value)
            )
        else:
            self._isDirectLoaded = True

    def setCoupledValues(self, values, hoys, source=None, state=None):
        """Set total and direct values for several hours of the year.

        Args:
            values: List of Illuminance values as tuples (total, direct).
            hoys: List of hours of the year that corresponds to input values.
            source: Name of the source of light. Only needed in case of multiple
                sources / window groups (default: None).
            state: State of the source if any (default: None).
        """
        if not (isinstance(values, types.GeneratorType) or
                isinstance(hoys, types.GeneratorType)):

            assert len(values) == len(hoys), \
                ValueError(
                    'Length of values [%d] is not equal to length of hoys [%d].'
                    % (len(values), len(hoys)))

        sid, stateid = self._createDataStructure(source, state)

        for hoy, value in izip(hoys, values):
            try:
                self._values[sid][stateid][hoy] = value[0], value[1]
            except TypeError:
                raise ValueError(
                    "Wrong input: {}. Input values must be of length of 2.".format(value)
                )
            except IndexError:
                raise ValueError(
                    "Wrong input: {}. Input values must be of length of 2.".format(value)
                )
        self._isDirectLoaded = True

    def value(self, hoy, source=None, state=None):
        """Get total value for an hour of the year."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return self._values[sid][stateid][hoy][0]
        except KeyError:
            raise ValueError('Invalid hoy input: {}'.format(hoy))

    def directValue(self, hoy, source=None, state=None):
        """Get direct value for an hour of the year."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return self._values[sid][stateid][hoy][1]
        except KeyError:
            raise ValueError('Invalid hoy input: {}'.format(hoy))
        else:
            self._isDirectLoaded = True

    def values(self, hoys, source=None, state=None):
        """Get illuminance values for several hours of the year."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return tuple(self._values[sid][stateid][hoy][0] for hoy in hoys)
        except KeyError as e:
            raise ValueError('Invalid hoy input: {}'.format(e))

    def directValues(self, hoys, source=None, state=None):
        """Get direct illuminance values for several hours of the year."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return tuple(self._values[sid][stateid][hoy][1] for hoy in hoys)
        except KeyError as e:
            raise ValueError('Invalid hoy input: {}'.format(e))

    def coupledValue(self, hoy, source=None, state=None):
        """Get total and direct values for an hoy."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return self._values[sid][stateid][hoy]
        except KeyError:
            raise ValueError('Invalid hoy input: {}'.format(hoy))

    def coupledValues(self, hoys, source=None, state=None):
        """Get total and direct values for several hours of year."""
        # find the id for source and state
        sid = self.sourceId(source)
        # find the state id
        stateid = self.blindStateId(source, state)

        try:
            return tuple(self._values[sid][stateid][hoy] for hoy in hoys)
        except KeyError as e:
            raise ValueError('Invalid hoy input: {}'.format(e))

    def coupledValueById(self, hoy, sourceId=None, stateId=None):
        """Get total and direct values for an hoy."""
        # find the id for source and state
        sid = sourceId or 0
        # find the state id
        stateid = stateId or 0

        try:
            return self._values[sid][stateid][hoy]
        except Exception as e:
            raise ValueError('Invalid input: {}'.format(e))

    def coupledValuesById(self, hoys, sourceId=None, stateId=None):
        """Get total and direct values for several hours of year by source id.

        Use this method to load the values if you have the ids for source and state.

        Args:
            hoys: A collection of hoys.
            sourceId: Id of source as an integer (default: 0).
            stateId: Id of state as an integer (default: 0).
        """
        sid = sourceId or 0
        stateid = stateId or 0
        try:
            return tuple(self._values[sid][stateid][hoy] for hoy in hoys)
        except Exception as e:
            raise ValueError('Invalid input: {}'.format(e))

    def combinedValueById(self, hoy, blindsStateIds=None):
        """Get combined value from all sources based on stateId.

        Args:
            hoy: hour of the year.
            blindsStateIds: List of state ids for all the sources for an hour. If you
                want a source to be removed set the state to -1.

        Returns:
            total, direct illuminance values.
        """
        total = 0
        direct = 0 if self._isDirectLoaded else None

        if not blindsStateIds:
            blindsStateIds = [0] * len(self._sources)

        assert len(self._sources) == len(blindsStateIds), \
            'There should be a state for each source. #sources[{}] != #states[{}]' \
            .format(len(self._sources), len(blindsStateIds))

        for sid, stateid in enumerate(blindsStateIds):

            if stateid == -1:
                t = 0
                d = 0
            else:
                try:
                    t, d = self._values[sid][stateid][hoy]
                except Exception as e:
                    raise ValueError('Invalid input: {}'.format(e))

            try:
                total += t
                direct += d
            except TypeError:
                # direct value is None
                pass

        return total, direct

    def combinedValuesById(self, hoys=None, blindsStateIds=None):
        """Get combined value from all sources based on stateId.

        Args:
            hoys: A collection of hours of the year.
            blindsStateIds: List of state ids for all the sources for input hoys. If you
                want a source to be removed set the state to -1.

        Returns:
            Return a generator for (total, direct) illuminance values.
        """
        hoys = hoys or self.hoys

        if not blindsStateIds:
            blindsStateIds = [[0] * len(self._sources)] * len(hoys)

        assert len(hoys) == len(blindsStateIds), \
            'There should be a list of states for each hour. #states[{}] != #hours[{}]' \
            .format(len(blindsStateIds), len(hoys))

        dirValue = 0 if self._isDirectLoaded else None
        for hoy in hoys:
            total = 0
            direct = dirValue

            for sid, stateid in enumerate(blindsStateIds[hoy]):
                if stateid == -1:
                    t = 0
                    d = 0
                else:
                    try:
                        t, d = self._values[sid][stateid][hoy]
                    except Exception as e:
                        raise ValueError('Invalid input: {}'.format(e))

                try:
                    total += t
                    direct += d
                except TypeError:
                    # direct value is None
                    pass

            yield total, direct

    def blindsState(self, hoys=None, blindsStateIds=None, *args, **kwargs):
        """Calculte blinds state based on a control logic.

        Overwrite self.logic to overwrite the logic for this point.

        Args:
            hoys: List of hours of year. If None default is self.hoys.
            blindsStateIds: List of state ids for all the sources for an hour. If you
                want a source to be removed set the state to -1. If not provided
                a longest combination of states from sources (window groups) will
                be used. Length of each item in states should be equal to number
                of sources.
            args: Additional inputs for self.logic. args will be passed to self.logic
            kwargs: Additional inputs for self.logic. kwargs will be passed to self.logic
        """
        hoys = hoys or self.hoys

        if blindsStateIds:
            # recreate the states in case the inputs are the names of the states
            # and not the numbers.
            sources = self.sources
            combs = [[c.strip() for c in str(cc).split(",")] for cc in blindsStateIds]

            combIds = copy.deepcopy(combs)

            # find state ids for each state
            try:
                for c, comb in enumerate(combs):
                    for count, source in enumerate(sources):
                        combIds[c][count] = self.blindStateId(source, comb[count])
            except IndexError:
                raise ValueError(
                    'Length of each state should be equal to number of sources: {}'
                    .format(len(sources))
                )
        else:
            combIds = self.longestStateIds

        print("Blinds combinations:\n{}".format(
              '\n'.join(str(ids) for ids in combIds)))

        # collect the results for each combination
        results = range(len(combIds))
        for count, state in enumerate(combIds):
            results[count] = tuple(self.combinedValuesById(hoys, [state] * len(hoys)))

        # assume the last state happens for all
        hoursCount = len(hoys)
        blindsIndex = [len(combIds) - 1] * hoursCount
        illValues = [None] * hoursCount
        dirValues = [None] * hoursCount
        success = [0] * hoursCount

        for h in hoys:
            for state in range(len(combIds)):
                ill, ill_dir = results[state][h]
                if not self.logic(ill, ill_dir, h, args, kwargs):
                    blindsIndex[h] = state
                    illValues[h] = ill
                    dirValues[h] = ill_dir
                    if state > 0:
                        success[h] = 1
                    break
            else:
                success[h] = -1
                illValues[h] = ill
                dirValues[h] = ill_dir

        blindsState = tuple(combIds[ids] for ids in blindsIndex)
        return blindsState, blindsIndex, illValues, dirValues, success

    def annualMetrics(self, DAThreshhold=None, UDIMinMax=None, blindsStateIds=None,
                      occSchedule=None):
        """Calculate annual metrics.

        Daylight autonomy, continious daylight autonomy and useful daylight illuminance.

        Args:
            DAThreshhold: Threshhold for daylight autonomy in lux (default: 300).
            UDIMinMax: A tuple of min, max value for useful daylight illuminance
                (default: (100, 2000)).
            blindsStateIds: List of state ids for all the sources for input hoys. If you
                want a source to be removed set the state to -1.
            occSchedule: An annual occupancy schedule.

        Returns:
            Daylight autonomy, Continious daylight autonomy, Useful daylight illuminance,
            Less than UDI, More than UDI
        """
        DAThreshhold = DAThreshhold or 300.0
        UDIMinMax = UDIMinMax or (100, 2000)
        udiMin, udiMax = UDIMinMax
        hours = self.hoys
        schedule = occSchedule or set(hours)
        DA = 0
        CDA = 0
        UDI = 0
        UDI_l = 0
        UDI_m = 0
        totalHourCount = len(hours)
        values = tuple(v[0] for v in self.combinedValuesById(hours, blindsStateIds))
        for v in values:
            if v not in schedule:
                totalHourCount -= 1
                continue
            if v >= DAThreshhold:
                DA += 1
                CDA += 1
            else:
                CDA += v / DAThreshhold

            if v < udiMin:
                UDI_l += 1
            elif v > udiMax:
                UDI_m += 1
            else:
                UDI += 1

        return DA / totalHourCount, CDA / totalHourCount, UDI / totalHourCount, \
            UDI_l / totalHourCount, UDI_m / totalHourCount

    def usefulDaylightIlluminance(self, UDIMinMax=None, blindsStateIds=None,
                                  occSchedule=None):
        """Calculate useful daylight illuminance.

        Args:
            UDIMinMax: A tuple of min, max value for useful daylight illuminance
                (default: (100, 2000)).
            blindsStateIds: List of state ids for all the sources for input hoys. If you
                want a source to be removed set the state to -1.
            occSchedule: An annual occupancy schedule.

        Returns:
            Useful daylight illuminance, Less than UDI, More than UDI
        """
        UDIMinMax = UDIMinMax or (100, 2000)
        udiMin, udiMax = UDIMinMax
        hours = self.hoys
        schedule = occSchedule or set(hours)
        UDI = 0
        UDI_l = 0
        UDI_m = 0
        totalHourCount = len(hours)
        values = tuple(v[0] for v in self.combinedValuesById(hours, blindsStateIds))
        for v in values:
            if v not in schedule:
                totalHourCount -= 1
                continue
            if v < udiMin:
                UDI_l += 1
            elif v > udiMax:
                UDI_m += 1
            else:
                UDI += 1

        return UDI / totalHourCount, UDI_l / totalHourCount, UDI_m / totalHourCount

    def daylightAutonomy(self, DAThreshhold=None, blindsStateIds=None,
                         occSchedule=None):
        """Calculate daylight autonomy and continious daylight autonomy.

        Args:
            DAThreshhold: Threshhold for daylight autonomy in lux (default: 300).
            blindsStateIds: List of state ids for all the sources for input hoys. If you
                want a source to be removed set the state to -1.
            occSchedule: An annual occupancy schedule.

        Returns:
            Daylight autonomy, Continious daylight autonomy
        """
        DAThreshhold = DAThreshhold or 300.0
        hours = self.hoys
        schedule = occSchedule or set(hours)
        DA = 0
        CDA = 0
        totalHourCount = len(hours)
        values = tuple(v[0] for v in self.combinedValuesById(hours, blindsStateIds))
        for v in values:
            if v not in schedule:
                totalHourCount -= 1
                continue
            if v >= DAThreshhold:
                DA += 1
                CDA += 1
            else:
                CDA += v / DAThreshhold

        return DA / totalHourCount, CDA / totalHourCount

    def ToString(self):
        """Overwrite .NET ToString."""
        return self.__repr__()

    def toRadString(self):
        """Return Radiance string for a test point."""
        return "%s %s" % (self.location, self.direction)

    def __repr__(self):
        """Print and analysis point."""
        return self.toRadString()
