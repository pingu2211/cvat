### Added

- A "Label templates" page where label templates can be created, edited and deleted.
  Templates are stored on the server: outside an organization they are private to their
  author, while templates created in an organization are shared with all of its members
  and can be edited by the author, the maintainers and the owner.
- Templates can also be started from a file exported by another CVAT instance. Task and
  project backups, exported annotations, and archives containing them are accepted, and
  the labels found in the file are used to fill in a new template. The annotations
  themselves are ignored.
