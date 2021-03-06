"""
Unit tests for user_management management commands.
"""
import itertools

import ddt
from django.contrib.auth.models import Group, User
from django.core.management import call_command, CommandError
from django.test import TestCase

TEST_EMAIL = 'test@example.com'
TEST_USERNAME = 'test-user'


@ddt.ddt
class TestManageUserCommand(TestCase):
    """
    Tests the `manage_user` command.
    """

    def test_user(self):
        """
        Ensures that users are created if they don't exist and reused if they do.
        """
        # pylint: disable=no-member
        self.assertEqual([], list(User.objects.all()))
        call_command('manage_user', TEST_USERNAME, TEST_EMAIL)
        user = User.objects.get(username=TEST_USERNAME)
        self.assertEqual(user.username, TEST_USERNAME)
        self.assertEqual(user.email, TEST_EMAIL)
        self.assertIsNotNone(user.profile)

        # check idempotency
        call_command('manage_user', TEST_USERNAME, TEST_EMAIL)
        self.assertEqual([(TEST_USERNAME, TEST_EMAIL)], [(u.username, u.email) for u in User.objects.all()])

    def test_remove(self):
        """
        Ensures that users are removed if they exist and exit cleanly otherwise.
        """
        # pylint: disable=no-member
        User.objects.create(username=TEST_USERNAME, email=TEST_EMAIL)
        self.assertEqual([(TEST_USERNAME, TEST_EMAIL)], [(u.username, u.email) for u in User.objects.all()])
        call_command('manage_user', TEST_USERNAME, TEST_EMAIL, '--remove')
        self.assertEqual([], list(User.objects.all()))

        # check idempotency
        call_command('manage_user', TEST_USERNAME, TEST_EMAIL, '--remove')
        self.assertEqual([], list(User.objects.all()))

    def test_wrong_email(self):
        """
        Ensure that the operation is aborted if the username matches an
        existing user account but the supplied email doesn't match.
        """
        # pylint: disable=no-member
        User.objects.create(username=TEST_USERNAME, email=TEST_EMAIL)
        with self.assertRaises(CommandError) as exc_context:
            call_command('manage_user', TEST_USERNAME, 'other@example.com')
        self.assertIn('email addresses do not match', str(exc_context.exception).lower())
        self.assertEqual([(TEST_USERNAME, TEST_EMAIL)], [(u.username, u.email) for u in User.objects.all()])

        # check that removal uses the same check
        with self.assertRaises(CommandError) as exc_context:
            call_command('manage_user', TEST_USERNAME, 'other@example.com', '--remove')
        self.assertIn('email addresses do not match', str(exc_context.exception).lower())
        self.assertEqual([(TEST_USERNAME, TEST_EMAIL)], [(u.username, u.email) for u in User.objects.all()])

    @ddt.data(*itertools.product([(True, True), (True, False), (False, True), (False, False)], repeat=2))
    @ddt.unpack
    def test_bits(self, initial_bits, expected_bits):
        """
        Ensure that the 'staff' and 'superuser' bits are set according to the
        presence / absence of the associated command options, regardless of
        any previous state.
        """
        initial_staff, initial_super = initial_bits
        User.objects.create(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            is_staff=initial_staff,
            is_superuser=initial_super
        )

        expected_staff, expected_super = expected_bits
        args = [opt for bit, opt in ((expected_staff, '--staff'), (expected_super, '--superuser')) if bit]
        call_command('manage_user', TEST_USERNAME, TEST_EMAIL, *args)
        user = User.objects.all().first()  # pylint: disable=no-member
        self.assertEqual(user.is_staff, expected_staff)
        self.assertEqual(user.is_superuser, expected_super)

    @ddt.data(*itertools.product(('', 'a', 'ab', 'abc'), repeat=2))
    @ddt.unpack
    def test_groups(self, initial_groups, expected_groups):
        """
        Ensures groups assignments are created and deleted idempotently.
        """
        groups = {}
        for group_name in 'abc':
            groups[group_name] = Group.objects.create(name=group_name)

        user = User.objects.create(username=TEST_USERNAME, email=TEST_EMAIL)
        for group_name in initial_groups:
            user.groups.add(groups[group_name])

        call_command('manage_user', TEST_USERNAME, TEST_EMAIL, '-g', *expected_groups)
        actual_groups = [group.name for group in user.groups.all()]
        self.assertEqual(actual_groups, list(expected_groups))

    def test_nonexistent_group(self):
        """
        Ensures the command does not fail if specified groups cannot be found.
        """
        user = User.objects.create(username=TEST_USERNAME, email=TEST_EMAIL)
        groups = {}
        for group_name in 'abc':
            groups[group_name] = Group.objects.create(name=group_name)
            user.groups.add(groups[group_name])

        call_command('manage_user', TEST_USERNAME, TEST_EMAIL, '-g', 'b', 'c', 'd')
        actual_groups = [group.name for group in user.groups.all()]
        self.assertEqual(actual_groups, ['b', 'c'])
