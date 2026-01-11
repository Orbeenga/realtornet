# scripts/migrate.py
"""
Database migration management script for RealtorNet.
Provides a convenient CLI wrapper around Alembic migrations.

Usage:
    python scripts/migrate.py run                    # Apply all pending migrations
    python scripts/migrate.py create "description"   # Create new migration
    python scripts/migrate.py rollback               # Rollback last migration
    python scripts/migrate.py rollback 2             # Rollback 2 migrations
    python scripts/migrate.py current                # Show current revision
    python scripts/migrate.py history                # Show migration history
"""

import os
import sys
import subprocess
from typing import NoReturn, Optional
from contextlib import contextmanager


@contextmanager
def migration_context():
    """
    Context manager for migration operations.
    Ensures correct working directory and Python path.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    old_cwd = os.getcwd()
    
    # Change to project root
    os.chdir(project_root)
    
    try:
        # Add project root to Python path if needed
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        yield project_root
        
    finally:
        # Restore original working directory
        os.chdir(old_cwd)


def run_alembic_command(args: list[str]) -> None:
    """
    Execute an Alembic command with error handling.
    
    Args:
        args: List of command arguments to pass to Alembic
        
    Raises:
        SystemExit: On command failure
    """
    try:
        subprocess.run(['alembic'] + args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Alembic command failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Alembic is not installed or not found in PATH.")
        print("Install with: pip install alembic")
        sys.exit(1)


def run_migrations() -> None:
    """
    Apply all pending migrations to the database.
    Equivalent to: alembic upgrade head
    """
    print("🔄 Applying migrations...")
    with migration_context():
        run_alembic_command(['upgrade', 'head'])
        print("✅ Migrations applied successfully!")


def create_migration(message: str) -> None:
    """
    Create a new migration with autogenerate.
    Equivalent to: alembic revision --autogenerate -m "message"
    
    Args:
        message: Description of the migration
    """
    print(f"📝 Creating migration: {message}")
    with migration_context():
        run_alembic_command(['revision', '--autogenerate', '-m', message])
        print(f"✅ Migration created: {message}")


def rollback_migrations(steps: int = 1) -> None:
    """
    Rollback the last N migrations.
    Equivalent to: alembic downgrade -N
    
    Args:
        steps: Number of migrations to rollback (default: 1)
    """
    print(f"⏪ Rolling back {steps} migration(s)...")
    with migration_context():
        run_alembic_command(['downgrade', f'-{steps}'])
        print(f"✅ Rolled back {steps} migration(s)")


def show_current() -> None:
    """
    Show current migration revision.
    Equivalent to: alembic current
    """
    print("📍 Current migration revision:")
    with migration_context():
        run_alembic_command(['current'])


def show_history() -> None:
    """
    Show migration history.
    Equivalent to: alembic history
    """
    print("📜 Migration history:")
    with migration_context():
        run_alembic_command(['history'])


def print_usage() -> NoReturn:
    """Print usage information and exit."""
    print(__doc__)
    sys.exit(1)


def main() -> None:
    """Main entry point for migration script."""
    if len(sys.argv) < 2:
        print_usage()
    
    command = sys.argv[1].lower()
    
    if command == 'run':
        run_migrations()
        
    elif command == 'create':
        if len(sys.argv) < 3:
            print("❌ Please provide a migration message")
            print("Usage: python scripts/migrate.py create 'description'")
            sys.exit(1)
        message = ' '.join(sys.argv[2:])
        create_migration(message)
        
    elif command == 'rollback':
        steps = 1
        if len(sys.argv) >= 3:
            try:
                steps = int(sys.argv[2])
            except ValueError:
                print(f"❌ Invalid number of steps: {sys.argv[2]}")
                sys.exit(1)
        rollback_migrations(steps)
        
    elif command == 'current':
        show_current()
        
    elif command == 'history':
        show_history()
        
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == '__main__':
    main()