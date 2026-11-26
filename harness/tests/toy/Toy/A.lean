/-! An ordinary file. -/

namespace Toy.A

def double (n : Nat) : Nat := n + n

theorem double_eq (n : Nat) : double n = 2 * n := by
  unfold double; omega

theorem double_double (n : Nat) : double (double n) = 4 * n := by
  simp only [double_eq]; omega

end Toy.A
