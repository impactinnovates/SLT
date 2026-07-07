# SharePoint List changes for the Initiative/Task hierarchy

The dashboard treats the Strategic Initiatives List as a two-level hierarchy using
fields that already exist, plus **one** new column.

## Fields used (already on the List)

| List column | Used as | Notes |
|---|---|---|
| `Task/Initiative` | row type | `Initiative` = SLT parent, `Task` = child. Blank rows are treated as Initiative. |
| `Owner` | task assignee | who a Task belongs to (a Leader or Member). |
| `Created By` | task creator | lets a Leader see tasks they assigned to their team. |
| `ID` | identity | the parent's `ID` is what a Task's `Parent ID` points to. |

## New column to add (one)

| Property | Value |
|---|---|
| **Name** | `Parent ID` |
| **Type** | Number (0 decimal places) |
| **Description** | The ID of the parent Initiative this Task rolls up to. Set by the dashboard; leave blank on Initiatives. |

Additive and safe - existing rows get a blank `Parent ID`. The dashboard sets it
automatically when you create a Task under an Initiative (you pick the parent; no
one types an ID). Status added to the live List on 2026-07-07.

## Roll-up behavior

For each Initiative, the app gathers Tasks whose `Parent ID` = the Initiative's `ID`
and computes:
- **rolled % complete** = mean of child task % complete
- **task risk** = any child Task is Behind or Blocked
- **effective %** = the Initiative's own % if SLT set one, else the rolled-up %

The internal (Graph) name of `Parent ID` will be confirmed by the probe when the
live connection is enabled, and mapped in `data/models.py` (`GRAPH_MAP`).
