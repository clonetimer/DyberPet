"""Use the exact PetConfig AST assignments to test role & mini-pet defaults.

A synthetic native role can call its action 'idle_01' rather than 'default'.
The original mini loader had KeyError('default') and returned a string for
prefall; both break valid licensed character packages at runtime.
"""
import ast
import types
import unittest
from pathlib import Path


def compiled_references(method_name):
    path = Path(__file__).resolve().parents[1] / "DyberPet" / "conf.py"
    root = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in root.body
               if isinstance(n, ast.ClassDef) and n.name == "PetConfig")
    method = next(n for n in cls.body
                  if isinstance(n, ast.FunctionDef) and n.name == method_name)
    scope = next(n for n in method.body if isinstance(n, ast.With))
    statements = scope.body

    def is_target(stmt, name):
        return (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Attribute)
                and isinstance(stmt.targets[0].value, ast.Name)
                and stmt.targets[0].value.id == "o"
                and stmt.targets[0].attr == name)

    start = next(i for i, n in enumerate(statements) if is_target(n, "default"))
    end = next(i for i, n in enumerate(statements)
               if i > start and is_target(n, "patpat")) + 1
    chosen = statements[start:end]
    return compile(ast.fix_missing_locations(ast.Module(
        body=chosen, type_ignores=[])), str(path), "exec")


class RoleActionDefaultRegression(unittest.TestCase):
    def setUp(self):
        self.actions = {name: object() for name in
                        ("idle_01", "falling_01", "drag_01", "pat_01")}

    def run_refs(self, method, conf):
        obj = types.SimpleNamespace()
        globals_ = dict(o=obj, conf_params=conf, act_dict=self.actions,
                        num_hp_states=4, fill_missing_hptier=lambda x: x)
        exec(compiled_references(method), globals_)
        return obj

    def test_minipet_optional_actions_use_real_default_name(self):
        obj = self.run_refs("init_subpet", {"default": "idle_01"})
        for name in ("default", "up", "down", "left", "right",
                     "on_floor", "drag", "fall", "prefall"):
            with self.subTest(action=name):
                self.assertIs(getattr(obj, name), self.actions["idle_01"])
        for act in obj.patpat.values():
            self.assertIs(act, self.actions["idle_01"])

    def test_prefall_follows_configured_fall_not_an_unresolved_string(self):
        obj = self.run_refs("init_subpet", {
            "default": "idle_01", "fall": "falling_01"})
        self.assertIs(obj.fall, self.actions["falling_01"])
        self.assertIs(obj.prefall, self.actions["falling_01"])
        self.assertFalse(isinstance(obj.prefall, str))

    def test_explicit_mini_animation_is_not_replaced(self):
        obj = self.run_refs("init_subpet", {
            "default": "idle_01", "drag": "drag_01", "patpat": "pat_01",
            "fall": "falling_01"})
        self.assertIs(obj.drag, self.actions["drag_01"])
        self.assertIs(obj.patpat[0], self.actions["pat_01"])
        self.assertIs(obj.prefall, self.actions["falling_01"])

    def test_main_role_optional_directions_also_use_real_default(self):
        obj = self.run_refs("init_config", {
            "default": "idle_01", "fall": "falling_01",
            "drag": "drag_01"})
        for name in ("up", "down", "left", "right", "on_floor"):
            self.assertIs(getattr(obj, name), self.actions["idle_01"])
        self.assertIs(obj.prefall, self.actions["falling_01"])
        self.assertIs(obj.patpat[3], self.actions["idle_01"])
        self.assertIsNone(obj.focus)


if __name__ == "__main__":
    unittest.main()
