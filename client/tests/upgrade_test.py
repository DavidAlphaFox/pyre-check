# Copyright (c) 2016-present, Facebook, Inc.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import itertools
import json
import pathlib
import unittest
from unittest.mock import MagicMock, call, mock_open, patch

from .. import upgrade


def _result(errors):
    def error_path(error):
        return error["path"]

    return itertools.groupby(sorted(errors, key=error_path), error_path)


class FixmeAllTest(unittest.TestCase):
    @patch.object(
        upgrade.Configuration, "find_project_configuration", return_value=None
    )
    def test_gather_local_configurations(self, _find_project_configuration) -> None:
        process = MagicMock()
        arguments = MagicMock()
        arguments.push_blocking_only = None

        def configuration_lists_equal(expected_configurations, actual_configurations):
            if len(expected_configurations) != len(actual_configurations):
                print(
                    "Expected {} configurations, got {} configurations".format(
                        len(expected_configurations), len(actual_configurations)
                    )
                )
                return False
            lists_equal = True
            for expected, actual in zip(expected_configurations, actual_configurations):
                if expected.root != actual.root:
                    print(
                        "Expected configuration with root {}, got root {}".format(
                            expected.root, actual.root
                        )
                    )
                    lists_equal = False
                elif expected.targets != actual.targets:
                    print(
                        "Expected configuration with targets {}, got targets {}".format(
                            expected.targets, actual.targets
                        )
                    )
                    lists_equal = False
                elif expected.source_directories != actual.source_directories:
                    print(
                        "Expected configuration with source_directories {}, \
                        got source_directories {}".format(
                            expected.source_directories, actual.source_directories
                        )
                    )
                    lists_equal = False
                elif expected.push_blocking != actual.push_blocking:
                    print(
                        "Expected configuration with push_blocking {}, \
                        got push_blocking {}".format(
                            expected.push_blocking, actual.push_blocking
                        )
                    )
                    lists_equal = False
            return lists_equal

        configurations_string = ""
        process.stdout = configurations_string.encode()
        with patch("subprocess.run", return_value=process):
            configurations = upgrade.Configuration.gather_local_configurations(
                arguments
            )
            self.assertEqual([], configurations)

        configurations_string = "path/to/.pyre_configuration.local"
        process.stdout = configurations_string.encode()
        configuration_contents = '{"targets":[]}'
        expected_configurations = [
            upgrade.Configuration(
                "path/to/.pyre_configuration.local", json.loads(configuration_contents)
            )
        ]
        with patch("subprocess.run", return_value=process):
            with patch("builtins.open", mock_open(read_data=configuration_contents)):
                configurations = upgrade.Configuration.gather_local_configurations(
                    arguments
                )
                self.assertTrue(
                    configuration_lists_equal(expected_configurations, configurations)
                )

        configurations_string = (
            "a/.pyre_configuration.local\nb/.pyre_configuration.local\n"
        )
        process.stdout = configurations_string.encode()
        configuration_contents = '{"targets":[],\n"coverage":true}'
        expected_configurations = [
            upgrade.Configuration(
                "a/.pyre_configuration.local", json.loads(configuration_contents)
            ),
            upgrade.Configuration(
                "b/.pyre_configuration.local", json.loads(configuration_contents)
            ),
        ]
        with patch("subprocess.run", return_value=process):
            with patch("builtins.open", mock_open(read_data=configuration_contents)):
                configurations = upgrade.Configuration.gather_local_configurations(
                    arguments
                )
                self.assertTrue(
                    configuration_lists_equal(expected_configurations, configurations)
                )

        arguments.push_blocking_only = True
        configurations_string = (
            "a/.pyre_configuration.local\nb/.pyre_configuration.local\n"
        )
        process.stdout = configurations_string.encode()
        configuration_contents = '{"targets":[],\n"coverage":true}'
        expected_configurations = [
            upgrade.Configuration(
                "a/.pyre_configuration.local", json.loads(configuration_contents)
            ),
            upgrade.Configuration(
                "b/.pyre_configuration.local", json.loads(configuration_contents)
            ),
        ]
        with patch("subprocess.run", return_value=process):
            with patch("builtins.open", mock_open(read_data=configuration_contents)):
                configurations = upgrade.Configuration.gather_local_configurations(
                    arguments
                )
                self.assertEqual([], configurations)

    @patch("subprocess.call")
    @patch("subprocess.run")
    def test_get_errors(self, run, call) -> None:
        configuration = upgrade.Configuration("path", {})
        configuration.get_errors()
        call.assert_not_called()
        assert run.call_count == 1

        call.reset_mock()
        run.reset_mock()

        configuration.targets = ["//target/..."]
        configuration.get_errors()
        assert call.call_count == 1
        assert run.call_count == 1


class FixmeTest(unittest.TestCase):
    @patch.object(pathlib.Path, "read_text")
    def test_fixme(self, path_read_text) -> None:
        arguments = MagicMock()
        arguments.comment = None
        arguments.max_line_length = 88

        upgrade.run_fixme(arguments, {})

        # Test single error.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [1]: description",
                    }
                ]
            )
            path_read_text.return_value = "  1\n2"
            upgrade.run_fixme(arguments, result)
            path_write_text.assert_called_once_with(
                "  # pyre-fixme[1]: description\n  1\n2"
            )

        # Test error with comment.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [1]: description",
                    }
                ]
            )
            path_read_text.return_value = "  1\n2"
            arguments.comment = "T1234"
            upgrade.run_fixme(arguments, result)
            arguments.comment = None
            path_write_text.assert_called_once_with("  # pyre-fixme[1]: T1234\n  1\n2")

        # Test multiple errors and multiple lines.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [1]: description",
                    },
                    {
                        "path": "path.py",
                        "line": 2,
                        "description": "Error [1]: description",
                    },
                    {
                        "path": "path.py",
                        "line": 2,
                        "description": "Error [2]: description",
                    },
                ]
            )
            path_read_text.return_value = "1\n2"
            upgrade.run_fixme(arguments, result)
            path_write_text.assert_called_once_with(
                "# pyre-fixme[1]: description\n1\n# pyre-fixme[1, 2]: description\n2"
            )

        # Test errors in multiple files.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [1]: description",
                    },
                    {
                        "path": "other.py",
                        "line": 2,
                        "description": "Error [2]: description",
                    },
                ]
            )
            path_read_text.return_value = "1\n2"
            upgrade.run_fixme(arguments, result)
            path_write_text.has_calls(
                [
                    call("# pyre-fixme[1]: description\n1\n2"),
                    call("1\n#pyre-fixme[2]: description\n2"),
                ]
            )

        # Test removal of extraneous ignore.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [0]: extraneous ignore",
                    }
                ]
            )
            path_read_text.return_value = "  # pyre-ignore[0]: [1, 2, 3]\n2"
            upgrade.run_fixme(arguments, result)
            arguments.comment = None
            path_write_text.assert_called_once_with("2")

        # Test removal of extraneous ignore (trailing comment).
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [0]: extraneous ignore",
                    }
                ]
            )
            path_read_text.return_value = "1# pyre-ignore[0]: [1, 2, 3]\n2"
            upgrade.run_fixme(arguments, result)
            arguments.comment = None
            path_write_text.assert_called_once_with("1\n2")

        # Test wrapping of long lines.
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            arguments_short = MagicMock()
            arguments_short.comment = None
            arguments_short.max_line_length = 35

            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 1,
                        "description": "Error [1]: description one, "
                        + "that has a pretty verbose text",
                    },
                    {
                        "path": "path.py",
                        "line": 2,
                        "description": "Error [2]: description-that-will-not-break-"
                        + "even-when-facing-adversities",
                    },
                    {
                        "path": "path.py",
                        "line": 3,
                        "description": "Error [3]: description.with "
                        + "mixed.separators.that should.also.break",
                    },
                    {
                        "path": "path.py",
                        "line": 4,
                        "description": "Error [4]: description starts short, "
                        + "but-then-has-a-very-long-type-name-or-similar "
                        + "that does not break",
                    },
                ]
            )
            path_read_text.return_value = "line 1\nline 2\nline 3\nline 4"
            upgrade.run_fixme(arguments_short, result)
            path_write_text.assert_called_once_with(
                """# pyre: description one,
# pyre: that has a pretty
# pyre-fixme[1]: verbose text
line 1
# pyre-fixme[2]: description-that-will-not-break-even-when-facing-adversities
line 2
# pyre: description.with
# pyre: mixed.separators.
# pyre: that should.also.
# pyre-fixme[3]: break
line 3
# pyre: description
# pyre: starts short,
# pyre: but-then-has-a-very-long-type-name-or-similar
# pyre: that does not
# pyre-fixme[4]: break
line 4"""
            )

        # Test removal of extraneous ignores (wrapping lines).
        with patch.object(pathlib.Path, "write_text") as path_write_text:
            result = _result(
                [
                    {
                        "path": "path.py",
                        "line": 3,
                        "description": "Error [0]: extraneous ignore",
                    },
                    {
                        "path": "path.py",
                        "line": 9,
                        "description": "Error [0]: extraneous ignore",
                    },
                    {
                        "path": "path.py",
                        "line": 13,
                        "description": "Error [0]: extraneous ignore",
                    },
                ]
            )
            path_read_text.return_value = """# pyre: description one,
# pyre: that has a pretty
# pyre-fixme[1]: verbose text
line 1
# pyre: other description with
# pyre-fixme[2]: wrapping lines
line 2
# pyre: yet other description with
# pyre-fixme[3]: wrapping lines
line 3

# pyre: long description
# pyre-fixme[4]: preceded by whitespace
line 4"""
            upgrade.run_fixme(arguments, result)
            path_write_text.assert_called_once_with(
                """line 1
# pyre: other description with
# pyre-fixme[2]: wrapping lines
line 2
line 3

line 4"""
            )
