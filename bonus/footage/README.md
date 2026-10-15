# bonus/footage/

The bonus (Patreon) video's recorded segments, named so NAME ORDER IS PLAY ORDER:
`A_intro.mov`, `B_wordle.mov`, ... The clips are gitignored (local, not synced);
git tracks only this README.

Import them into the `<Video> Bonus` DaVinci project (a `Footage` bin), and with
`--timeline` lay any not yet placed onto the end of the timeline, in order:

    python -m bpkfigures.footage bonus --timeline

Re-running after adding a clip imports just the new one.
