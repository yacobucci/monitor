import logging

from isodate import parse_duration

from .tools.mixins import SchedulableMixin

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Calibration(SchedulableMixin):
    def __init__(self, target, conf_dict, target_obj, sources, store, scheduler):
        self._last = None
        self._policy = None
        self._policy_interval = None
        self._target_obj = None

        self._target = target
        self._conf = conf_dict
        self._sources = sources
        self._store = store
        self._scheduler = scheduler
        self._job = None

        # XXX error checking, error checking, error checking...
        if self._conf['target']['where'] == 'real':
            self._target_obj = target_obj.real_device
        elif self._conf['target']['where'] == 'abstract':
            self._target_obj = target_obj
        else:
            raise NotImplementedError

        if self._conf['policy']['aggregation'] == 'average':
            self._policy = self._measure_average
        else:
            raise NotImplementedError
        self._policy_interval = 'once' if self._conf['policy']['interval'] == 'once' else \
                parse_duration(self._conf['policy']['interval']).seconds

        logger.debug('config: interval %s policy %s object %s',
                     self._policy_interval, self._policy, self._target_obj)

    def start(self, immediate: bool) -> None:
        if self._policy_interval == 'once':
            self._job = 'finished'
            self.calibrate()
        elif self._job is not None:
            return

        if immediate:
            self.calibrate()
        self._job = self._scheduler.add_job(self.calibrate, 'interval',
                                            seconds=self._policy_interval)

    def stop(self):
        if self._job is None or self._job == 'finished':
            return

        self._job.remove()
        self._job = None

    def _measure_average(self):
        l = float(len(self._sources))
        v = 0.0
        for s in self._sources:
            v = v + s.measure
        v = v / l
        return v

    def _measure_first(self):
        raise NotImplementedError

    def _measure_specific(self):
        raise NotImplementedError

    def calibrate(self):
        logger.debug('Calibration.calibrate source %s setting %s for %s',
                     self._conf['source']['device'], self._conf['target']['property'],
                     self._target)
        value = self._policy()
        if self._last is None or self._last != value:
            logger.info('found change from %s to %s', self._last, value)
            logger.debug('will pull new value %s from %s.measure', value,
                         self._conf['source']['device'])
            logger.debug('will set value %s to %s.%s with %s device', value, self._target,
                         self._conf['target']['property'], self._conf['target']['where'])

            setattr(self._target_obj, self._conf['target']['property'], value)
            self._last = value
        else:
            logger.debug('no changes in %s', self._conf['target']['property'])
