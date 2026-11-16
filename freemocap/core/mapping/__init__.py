"""Tracker→standard-human landmark mappings, owned by freemocap.

The mapping classes were copied from skellytracker (sfn26), which no longer owns them
in 2.0.0. A mapping is applied to triangulated 3D points.

The snapshot rule: a recording saves the `TrackerMappingSnapshot` of each mapping it
used (`RecordedModel.mappings`), and the snapshot names the tracker points it reads.
A snapshot and the channels it maps come from ONE recording, so an old snapshot (old
tracker names) and a new snapshot (new point names) coexist with no version field and
no name translation. Thus the four snapshot fields `entries`, `prefix`,
`known_tracker_keypoints` and `passthrough` keep their names, types and order: a change
breaks the reading and the fingerprints of saved recordings.
"""
