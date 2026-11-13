"""联锁表、工况表的列定义：三种写法和空表回退。"""
import contextlib
import io
import unittest

import _util  # noqa: F401

import colconv


def model(**conv):
    return {'conventions': conv,
            'interlocks': [{'id': 'I-01', 'actions': {'valve': '关', 'heat': '断'}}],
            'modes': [{'id': 'M1', 'name': '待机', 'valve': '关', 'permissive': '无', 'exit': '无'}]}


def quiet(fn, m):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        return fn(m), err.getvalue()


class Columns(unittest.TestCase):
    def test_triples(self):
        cols, _ = quiet(colconv.action_columns, model(action_columns=[['valve', '阀门动作', '阀']]))
        self.assertEqual(cols, [['valve', '阀门动作', '阀']])

    def test_pairs_get_short_name(self):
        cols, _ = quiet(colconv.action_columns, model(action_columns=[['valve', '阀门动作']]))
        self.assertEqual(cols, [['valve', '阀门动作', '阀门动作']])

    def test_string_keys_use_action_names(self):
        cols, err = quiet(colconv.action_columns, model(action_columns=['valve', 'heat'], action_names={'valve': '阀门动作'}))
        self.assertEqual([c[:2] for c in cols], [['valve', '阀门动作'], ['heat', 'heat']])
        self.assertEqual(err, '')

    def test_empty_falls_back_to_keys_with_warning(self):
        cols, err = quiet(colconv.action_columns, model(action_columns=[]))
        self.assertEqual([c[0] for c in cols], ['valve', 'heat'])
        self.assertIn('action_columns', err)

    def test_no_other_project_headers(self):
        cols, _ = quiet(colconv.action_columns, model())
        self.assertFalse(any('XV-101' in c[1] for c in cols))

    def test_mode_columns_end_with_permissive_and_exit(self):
        cols, _ = quiet(colconv.mode_columns, model(mode_columns=[['valve', '阀门']]))
        self.assertEqual([c[0] for c in cols], ['valve', 'permissive', 'exit'])
        cols, _ = quiet(colconv.mode_columns, model())
        self.assertEqual([c[0] for c in cols], ['valve', 'permissive', 'exit'])


if __name__ == '__main__':
    unittest.main()
