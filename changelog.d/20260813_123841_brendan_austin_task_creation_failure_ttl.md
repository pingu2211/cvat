### Fixed

- Failed task creation RQ jobs are now kept for the configured import failure TTL
  instead of the queue default, because the manager overrode a misspelled property name
  (<https://github.com/pingu2211/cvat/pull/11>)
