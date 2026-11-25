/-
  Semantic instance audit.

  The regex scanner in `instance-scan.py` finds *declarations*; this reads the
  elaborator's own instance table (`Meta.instanceExtension`), so it sees exactly
  what instance search will see: discrimination keys, priority, scope, module.

  Usage: generate a wrapper
      import <Module>
      <this file>
      #instance_audit
  and run `lake env lean wrapper.lean`.  Output is TSV:
      name  module  priority  attrKind  keys  type

  The keys are `DiscrTree.Key`s: `const MeasurableSpace, const Matrix` means a
  concrete key; `const Module, *` means a wildcard key (first argument is a
  variable), which costs synthesis time but does not shadow.
-/
import Lean

open Lean Meta Elab Command

namespace InstanceAudit

private def keyStr : DiscrTree.Key → String
  | .star => "*"
  | .other => "?"
  | .lit _ => "lit"
  | .fvar _ i => s!"fvar:{i}"
  | .const n _ => n.toString
  | .arrow => "->"
  | .proj s i j => s!"proj:{s}.{i}.{j}"

private def attrStr : AttributeKind → String
  | .global => "global"
  | .scoped => "scoped"
  | .local => "local"

/-- Print every instance in the current environment as TSV. -/
elab "#instance_audit" : command => do
  let env ← getEnv
  let insts := Meta.instanceExtension.getState env
  let mut n := 0
  for (name, entry) in insts.instanceNames.toList do
    let module :=
      match env.getModuleIdxFor? name with
      | some idx => (env.header.moduleNames[idx]!).toString
      | none => "<none>"
    let ty ← liftTermElabM do
      match env.find? name with
      | some ci => return (toString (← Meta.ppExpr ci.type))
      | none => return "<missing>"
    let keys := entry.keys.map keyStr |>.toList
    let ty := (ty.replace "\n" " ").replace "\t" " "
    IO.println s!"{name}\t{module}\t{entry.priority}\t{attrStr entry.attrKind}\t{String.intercalate "," keys}\t{ty}"
    n := n + 1
  IO.println s!"# total={n}"

end InstanceAudit
