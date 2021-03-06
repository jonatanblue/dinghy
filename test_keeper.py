#!/usr/bin/env python

import logging
import unittest
import os
import glob
import shutil
import tarfile
import keeper
from keeper import Keeper

# Enable verbose logs for tests
logger = logging.getLogger()
logger.level = logging.DEBUG

# Get current directory
BASE_DIRECTORY = os.getcwd()


# Override rundeck service check for unittests
def rundeck_is_running(arg):
    return False


Keeper._rundeck_is_running = rundeck_is_running


class MockedKeeper(Keeper):
    def __init__(self, *args):
        pass


class TestKeeper(unittest.TestCase):
    """Tests for `keeper.py`"""

    def setUp(self):
        """Set up defaults for all tests"""
        self.maxDiff = None

    def _create_dir(self, path):
        """Creates directory"""
        if not os.path.exists(path):
            os.makedirs(path)

    def _purge_directory(self, path):
        """Purges a directory and all its subdirectories

        WARNING: This will recursively delete the directory and all
        subdirectories forever.
        """
        shutil.rmtree(path)

    def _list_files_in_tar(self, path):
        """Returns list of all file paths inside a tar file"""
        with tarfile.open(path, 'r:gz') as archive:
            return archive.getnames()

    def test_instantiating(self):
        """Test that Keeper class can be instantiated"""
        directories = [
            "/var/lib/rundeck/data",          # database
            "/var/lib/rundeck/logs",          # execution logs (by far biggest)
            "/var/lib/rundeck/.ssh",          # ssh keys
            "/var/lib/rundeck/var/storage",   # key storage files and metadata
            "/var/rundeck/projects"           # project definitions
        ]
        Keeper(system_directories=directories)

    def test_has_overlap(self):
        """Test that overlap check works"""
        overlapping_dirs = [
            "/tmp/a/b",
            "/tmp/a"
        ]
        keeper = MockedKeeper()
        self.assertTrue(keeper._has_duplicate_or_overlap(overlapping_dirs))

    def test_has_overlap_reverse(self):
        """Test that overlap check works"""
        overlapping_dirs = [
            "/tmp/a",
            "/tmp/a/b"
        ]
        keeper = MockedKeeper()
        self.assertTrue(keeper._has_duplicate_or_overlap(overlapping_dirs))

    def test_has_duplicate(self):
        """Test that duplicate check works"""
        duplicate_dirs = [
            "/tmp/a/b",
            "/tmp/a/b"
        ]
        keeper = MockedKeeper()

        self.assertTrue(keeper._has_duplicate_or_overlap(duplicate_dirs))

    def test_valid_path_list(self):
        """Test that a valid path list is valid according to check"""
        valid_dirs = [
            "/tmp/a/b/c",
            "/tmp/a/b/d",
            "/tmp/q",
            "/var/troll"
        ]

        keeper = MockedKeeper()

        self.assertFalse(keeper._has_duplicate_or_overlap(valid_dirs))

    def test_raises_exception_on_relative_paths(self):
        """Test that relative paths raise an exception"""
        contains_relative_paths = [
            "some/path/here",
            "some/other/path",
            "/this/is/valid/though"
        ]
        with self.assertRaises(Exception):
            Keeper(system_directories=contains_relative_paths)

    def test_raises_exception_on_overlapping_dirs(self):
        """Test that exception is raised for overlapping dirs

        Passing overlapping directories should raise an exception.
        For example /tmp/a/b/c,/tmp/a/b should fail
        """
        # Set bad directories
        bad_directories = [
            "/tmp/keeper_python_unittest_raises/a/b/c",
            "/tmp/keeper_python_unittest_raises/a/b"
        ]
        # Set sails
        with self.assertRaises(Exception):
            Keeper(system_directories=bad_directories)

    def test_raises_exception_on_overlapping_dirs_reversed(self):
        """Test that exception is raised for overlapping dirs.

        For example /tmp/a/b,/tmp/a/b/c should fail
        """
        # Set bad directories
        bad_directories = [
            "/tmp/keeper_python_unittest_raises/a/b",
            "/tmp/keeper_python_unittest_raises/a/b/c"
        ]
        # Set sails
        with self.assertRaises(Exception):
            Keeper(system_directories=bad_directories)

    def test_backup(self):
        """Test creating a backup file from a set of directories"""
        cwd = os.getcwd()
        # Set paths
        file_paths = [
            cwd + "/tmp/keeper_test_backup/house/room/file1.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/file2.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/file3.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer/file4",
            cwd + "/tmp/keeper_test_backup/house/room/locker/file5.txt"
        ]
        folder_paths_to_create = [
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer",
            cwd + "/tmp/keeper_test_backup/house/room/locker"
        ]
        directories_to_backup = [
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer",
            cwd + "/tmp/keeper_test_backup/house/room/locker"
        ]
        files_expected_in_tar = [
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/desk/drawer"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/desk/drawer/file4"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/locker"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/locker/file5.txt"
            )
        ]

        keeper = Keeper(system_directories=directories_to_backup)

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup test
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        keeper.backup(
            destination_path=cwd + "/tmp/keeper_test_backup",
            filename="backup_test.tar.gz"
        )

        # Get list of all file paths inside tar file
        files_in_tar = self._list_files_in_tar(
            cwd + "/tmp/keeper_test_backup/backup_test.tar.gz")

        # tar file can't be empty
        self.assertNotEqual(len(files_in_tar), 0)

        # Normpath the paths
        # NOTE: I don't know why this is necessary
        files_expected_in_tar = [
            os.path.normpath(p) for p in files_expected_in_tar
        ]
        files_in_tar = [
            os.path.normpath(p) for p in files_in_tar
        ]

        # Compare tar file and list of files
        self.assertEqual(set(files_expected_in_tar), set(files_in_tar))

        # Recursively remove all directories and files used in test
        self._purge_directory(cwd + "/tmp/keeper_test_backup")

    def test_backup_skips_missing_dir(self):
        """Test that missing directory is skipped"""
        cwd = os.getcwd()
        # Set paths
        file_paths = [
            cwd + "/tmp/keeper_test_backup/house/room/file1.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/file2.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/file3.txt",
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer/file4",
            cwd + "/tmp/keeper_test_backup/house/room/locker/file5.txt"
        ]
        folder_paths_to_create = [
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer",
            cwd + "/tmp/keeper_test_backup/house/room/locker"
        ]
        directories_to_backup = [
            cwd + "/tmp/keeper_test_backup/house/room/desk/drawer",
            cwd + "/tmp/keeper_test_backup/house/room/locker",
            cwd + "/tmp/keeper_test_backup/ghosthouse"  # this does not exist
        ]
        files_expected_in_tar = [
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/desk/drawer"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/desk/drawer/file4"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/locker"
            ),
            os.path.join(
                cwd.strip("/"),
                "tmp/keeper_test_backup/house/room/locker/file5.txt"
            )
        ]

        keeper = Keeper(system_directories=directories_to_backup)

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup test
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        keeper.backup(
            destination_path=cwd + "/tmp/keeper_test_backup",
            filename="backup_test.tar.gz"
        )

        # Get list of all file paths inside tar file
        files_in_tar = self._list_files_in_tar(
            cwd + "/tmp/keeper_test_backup/backup_test.tar.gz")

        # tar file can't be empty
        self.assertNotEqual(len(files_in_tar), 0)

        # Normpath the paths
        # NOTE: I don't know why this is necessary
        files_expected_in_tar = [
            os.path.normpath(p) for p in files_expected_in_tar
        ]
        files_in_tar = [
            os.path.normpath(p) for p in files_in_tar
        ]

        # Compare tar file and list of files
        self.assertEqual(set(files_expected_in_tar), set(files_in_tar))

        # Recursively remove all directories and files used in test
        self._purge_directory(cwd + "/tmp/keeper_test_backup")

    def test_restore(self):
        """Test restoring a set of directories and files from a backup file"""
        # Set paths
        cwd = os.getcwd()
        file_paths = [
            cwd + "/tmp/keeper_test_restore/hotel/lobby/file1.txt",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/file2.txt",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/file3.txt",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/drawer/f4",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/locker/file5.txt"
        ]
        folder_paths_to_create = [
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/drawer/",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/locker"
        ]
        directories_to_backup = [
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/drawer/",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/locker/"
        ]
        files_expected_in_restore = [
            cwd + "/tmp/keeper_test_restore/hotel/lobby/locker/file5.txt",
            cwd + "/tmp/keeper_test_restore/hotel/lobby/desk/drawer/f4"
        ]

        keeper = Keeper(system_directories=directories_to_backup)

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        keeper.backup(
            destination_path=cwd + "/tmp/keeper_test_restore",
            filename="restore_test.tar.gz"
        )

        # Purge the source directory
        self._purge_directory(cwd + "/tmp/keeper_test_restore/hotel")

        # Restore
        keeper.restore(
            cwd + "/tmp/keeper_test_restore/restore_test.tar.gz")

        # List all directories
        restored = cwd + "/tmp/keeper_test_restore/hotel"
        files_found = []
        for root, dirs, files in os.walk(restored):
            for f in files:
                files_found.append(os.path.join(root, f))

        self.assertEqual(set(files_found), set(files_expected_in_restore))

        # Clean up test files and directories
        self._purge_directory(cwd + "/tmp/keeper_test_restore")

    def test_restore_check_content(self):
        """Test restoring a file and check contents"""
        # Set paths
        cwd = os.getcwd()
        file_paths = [
            cwd + "/tmp/keeper_test_r_check/a/b/file1.txt",
            cwd + "/tmp/keeper_test_r_check/a/b/c/file2.txt",
            cwd + "/tmp/keeper_test_r_check/a/b/c/file3.txt",
            cwd + "/tmp/keeper_test_r_check/a/b/c/e/f4",
            cwd + "/tmp/keeper_test_r_check/a/b/d/file5.txt"
        ]
        folder_paths_to_create = [
            cwd + "/tmp/keeper_test_r_check/a/b/c/e/",
            cwd + "/tmp/keeper_test_r_check/a/b/d"
        ]
        directories_to_backup = [
            cwd + "/tmp/keeper_test_r_check/a/b/d/"
        ]
        file_expected_in_restore = os.path.join(
            cwd + "/tmp/keeper_test_r_check/a/b/d/file5.txt"
        )

        keeper = Keeper(system_directories=directories_to_backup)

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        keeper.backup(
            destination_path=cwd + "/tmp/keeper_test_r_check",
            filename="restore_test.tar.gz"
        )

        # Purge the source directory
        self._purge_directory(cwd + "/tmp/keeper_test_r_check/a")

        # Restore
        keeper.restore(
            cwd + "/tmp/keeper_test_r_check/restore_test.tar.gz")

        # Get file contents
        with open(file_expected_in_restore, 'r') as restored_file:
            content = restored_file.read()
            logging.debug("content " + content)

        self.assertEqual(content, "lorem ipsum\n")

        # Clean up test files and directories
        self._purge_directory(cwd + "/tmp/keeper_test_r_check")

    def test_restore_does_not_overwrite(self):
        """Test that existing files are not overwritten by restore"""
        cwd = os.getcwd()
        base = cwd + "/tmp/keeper_python_unittest_restore_no_overwrite"
        # Set paths
        file_paths = [
            base + "/hotel/lobby/file1.txt",
            base + "/hotel/lobby/desk/file2.txt",
            base + "/hotel/lobby/desk/file3.txt",
            base + "/hotel/lobby/desk/drawer/f4",
            base + "/hotel/lobby/locker/file5.txt"
        ]
        folder_paths_to_create = [
            base + "/hotel/lobby/desk/drawer/",
            base + "/hotel/lobby/locker"
        ]
        directories_to_backup = [
            base + "/hotel/lobby/desk/drawer/",
            base + "/hotel/lobby/locker/"
        ]
        files_expected_in_restore = [
            base + "/hotel/lobby/desk/drawer/f4",
            base + "/hotel/lobby/locker/file5.txt"
        ]

        keeper = Keeper(system_directories=directories_to_backup)

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        keeper.backup(
            destination_path=base,
            filename="restore_test.tar.gz"
        )

        # Write to files again
        for name in files_expected_in_restore:
            with open(name, "w") as file_handle:
                file_handle.write("new version\n")

        # Restore should raise exception on existing file
        with self.assertRaises(Exception):
            keeper.restore(base + "/restore_test.tar.gz")

        # Get file contents
        files_content = []
        for name in files_expected_in_restore:
            with open(name, "r") as file_handle:
                content = file_handle.read()
                files_content.append(content)

        self.assertEqual(
            files_content,
            [
                "new version\n",
                "new version\n"
            ]
        )

        # Purge the test directory
        self._purge_directory(base)

    def test_backup_file_name_different_for_partial(self):
        """Test that partial backup file is named correctly

        If there is a directory override, the file should have
        "partial" in the name
        """
        # Set paths
        cwd = os.getcwd()
        base = cwd + "/tmp/keeper_python_unittest_partial_name"
        file_paths = [
            base + "/a/b/c.txt",
            base + "/q/r.txt"
        ]
        folder_paths_to_create = [
            base + "/a/b",
            base + "/q"
        ]

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup test
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        args = keeper.parse_args([
            '--dirs=' + cwd + '/tmp/keeper_python_unittest_partial_name/a/b',
            'backup',
            '--dest', 'tmp/keeper_python_unittest_partial_name'
        ])
        keeper.main(args)

        # Get filename
        archive_filename = glob.glob(base + "/*.tar.gz")[0]

        self.assertTrue("partial" in archive_filename)

        # Recursively remove all directories and files used in test
        self._purge_directory(cwd + "/tmp/keeper_python_unittest_partial_name")

    def test_restore_subset_directories(self):
        """Test restoring a subset of directories"""
        # Set paths
        cwd = os.getcwd()
        base = cwd + "/tmp/keeper_python_unittest_restore_subset"
        file_paths = [
            base + "/a/b/file1.txt",
            base + "/a/b/c/file2.txt",
            base + "/a/b/c/file3.txt",
            base + "/a/b/c/e/file4.txt",
            base + "/a/b/d/file5.txt"
        ]
        folder_paths_to_create = [
            base + "/a/b/c/e/",
            base + "/a/b/d"
        ]
        files_expected_in_restore = [
            base + "/a/b/c/e/file4.txt"
        ]

        # Create all directories
        for path in folder_paths_to_create:
            self._create_dir(path)

        # Create all files for backup
        for path in file_paths:
            # Create file
            with open(path, "w") as file_handle:
                file_handle.write("lorem ipsum\n")

        # Create backup
        args = keeper.parse_args([
            '--dirs=' + base + '/a/b',
            'backup',
            '--dest', base,
            '--filename', "test.tar.gz"
        ])
        keeper.main(args)

        # Purge the source directory
        self._purge_directory(base + "/a")

        # Restore
        args = keeper.parse_args([
            '--dirs=' + base + '/a/b/c/e',
            'restore',
            '--file=' + base + '/test.tar.gz'
        ])
        keeper.main(args)

        # List all directories
        restored = base + "/a"
        files_found = []
        for root, dirs, files in os.walk(restored):
            for f in files:
                files_found.append(os.path.join(root, f))

        self.assertEqual(set(files_found), set(files_expected_in_restore))

        # Clean up directory
        self._purge_directory(base)
