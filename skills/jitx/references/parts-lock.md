# The parts lock: stale entries and cleanup

`parts.lock.json` pins each resolved passive so a rebuild gives the same board. A build replays the entries its queries match and writes new ones for the rest; nothing ever removes an entry. Entries no query uses pile up. Clean them up with [`scripts/prune_lock.py`](../scripts/prune_lock.py), which removes only those, and do not delete the whole lock to get rid of them.

## Stale entries

An entry is keyed on the query's digest, the provider chain's label (`main`, `chain-2`) and the query's `lock_scope`. An entry no current query claims is stale. Four things leave one:

- a component removed from the design;
- a query edited so that its old part no longer satisfies it (when the old part still does, the build adopts the entry and nothing is left over);
- a test design, such as a `jitx.test.TestCase` run from the project root, which writes the project's lock as a build does;
- another chain: a different `chain` in `pyproject.toml`, or a `PartSource` set on a design. These entries are not stale in the same sense. Switching back to that chain restores their parts.

Stale entries do not change what a build places. They do two kinds of harm. A search of the lock (for `IDEAL-`, for an MPN list, for an approval list) finds parts the board does not use, so a lock search is not evidence about the board: read the parts from the design itself. And an edited query can adopt a leftover entry whose part still satisfies it, so a part the user moved away from can come back.

## Cleanup

Clean the lock before any step that reads it (an approval list, an `IDEAL-` search), and after a component is removed or a test design is run in the project. From the project root, with the project's Python, name every design the lock serves:

```bash
python <path to this skill>/scripts/prune_lock.py <module.path.DesignClass> [<another design> ...]
```

It elaborates each design under the `replay` lock mode, which writes nothing and asks no provider, and lists each entry no named design claimed, with its chain, part and query. It changes nothing. If any query does not replay (a component added or edited since the last build), it prints those queries and exits 1: run `jitx build` on every design, then run it again. Exit 2 means a usage error, an unreadable lock, or a design that did not import or build: fix that first.

Then:

1. Make sure the lock is committed, or commit it with the user's agreement, so the cleanup can be undone. The script also copies the lock to `parts.lock.json.bak` before it writes.
2. Show the user the listed entries. Run the same command with `--apply`. It removes the stale entries and nothing else; the rest of the file is byte for byte what the build wrote.
3. Entries under a chain no named design uses are listed as kept. Remove them with `--remove-chain <label>` only when the user says that chain will not come back.
4. Run `jitx build <design>` and `jitx design export parts-check <design> --fail all`. Show the user `git diff parts.lock.json`: it should hold only removed lines. A rebuild that adds lines means a removed entry was in use, so restore the backup and report it.

A design left off the command has its entries listed as stale: name a test design alongside the main one when the user wants its entries kept.

## Care

The whole lock is the record of every part already chosen. Deleting it re-resolves every query, and the chain can answer with different parts and footprints than the ones placed, routed or approved. On a design with placed, routed or approved parts, never delete the whole lock without the user's say-so, and tell them first that every passive will be chosen again. Remove only entries the design does not use, and leave another chain's entries unless the user says otherwise.

Two re-resolves are deliberate:

- The user's list replaces the stand-in CSV. Delete `parts.lock.json` and rebuild. The lock keys a CSV on its path, so a file overwritten in place re-resolves nothing; re-resolving every part against the user's list is what the user asked for.
- A row is added for a part that resolved `IDEAL-`. Adding the row alone changes nothing: the lock keeps the ideal part it pinned. Run the cleanup first, so the query cannot adopt a leftover entry, then delete from `entries` the one entry whose `identity.mpn` is that `IDEAL-` part, and rebuild. That query resolves against the new row and every other part stays pinned.
