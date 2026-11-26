-- A file of the module system: its proofs live in the private part of the .olean.
module

public section

namespace Toy.B

theorem add_comm' (a b : Nat) : a + b = b + a := Nat.add_comm a b

private theorem helper (xs : List Nat) : (xs ++ []).length = xs.length := by simp

theorem length_append_nil (xs : List Nat) : (xs ++ []).length = xs.length := helper xs

end Toy.B
