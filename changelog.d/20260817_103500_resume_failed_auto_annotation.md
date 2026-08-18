### Added

- A "Resume" action on a failed automatic annotation run, which continues it from the
  frame its results were last saved at rather than running the whole task or job again.
  The point to continue from is recorded on the server as the results are written, so
  the frames that were annotated but not yet saved are redone instead of being lost,
  and a resumed run never removes the existing annotations. Failed runs now stay listed
  until their queue entry expires, which was raised from 3 hours to 7 days so that a run
  left going overnight is still resumable the next morning.
