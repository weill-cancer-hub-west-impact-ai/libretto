#!/usr/bin/env python3
"""
Admin Script for Libretto

This script allows you to interactively manage users, projects, and user-project access
in the Libretto database.

Usage:
    python admin.py <database_connection_string>

Example:
    python admin.py sqlite:///./databases/example_interactions.db
"""

import sys
import os
import getpass
import argparse
from typing import Optional, Dict, Any, List
from libretto.database import LLMExtractDatabase
from libretto.types import Project
import bcrypt
import sqlalchemy as sa

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed.encode("utf-8"),
    )

def collect_environment_variables(current_vars: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """Collect environment variables interactively from user input."""
    print("\nEnvironment Variables:")
    env_vars = current_vars.copy() if current_vars else {}

    if current_vars:
        print("Current variables:")
        for key, value in current_vars.items():
            print(f"  {key}={value}")
        print()

        while True:
            var_input = input("Enter the name of an environment variable to DELETE, or press enter to skip this step: ").strip()
            if not var_input: 
                break

            if key not in env_vars:
                print("Key not in environment variable list.")
                continue

            del env_vars[key]
            print("Removed:", key)

    while True:
        var_input = input("Enter an environment variable to ADD in the format KEY=VALUE, or press enter to stop: ").strip()

        if not var_input:
            break

        if '=' not in var_input:
            print("Invalid format. Please use KEY=VALUE format.")
            continue

        key, value = var_input.split('=', 1)
        key = key.strip()
        value = value.strip()

        if not key:
            print("Key cannot be empty.")
            continue

        if key in env_vars:
            overwrite = input(f"Key '{key}' already exists with value '{env_vars[key]}'. Overwrite? (y/n): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                continue

        env_vars[key] = value
        print(f"Added: {key}={value}")

    return env_vars if env_vars else None

def list_users(db: LLMExtractDatabase) -> None:
    """List all users in the database."""
    users = db.list_users()

    if not users:
        print("\nNo users found in the database.")
        return

    print(f"\n{'ID':<5} {'Username':<20} {'Created At':<28} {'Last Login':<28} {'Admin?':<7}")
    print("-" * 90)

    for user in users:
        last_login = user.get('last_login', 'Never') or 'Never'
        print(f"{user['id']:<5} {user['username']:<20} {user['created_at']:<28} {last_login:<28} {'yes' if user['is_admin'] else 'no':<7}")

    print(f"\nTotal users: {len(users)}")

def create_user(db: LLMExtractDatabase) -> None:
    """Interactively create a new user."""
    print("\n=== Create New User ===")

    while True:
        username = input("Enter username: ").strip()
        if not username:
            print("Username cannot be empty.")
            continue

        existing_user = db.get_user_by_username(username)
        if existing_user:
            print(f"Error: Username '{username}' already exists.")
            continue

        break

    while True:
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Passwords do not match.")
            continue

        break

    admin_input = input("Make admin user? (y/n): ").strip().lower()
    is_admin = admin_input in ['y', 'yes']

    password_hash = get_password_hash(password)
    user_id = db.create_user(username, password_hash, is_admin=is_admin)
    print(f"\nUser '{username}' created successfully with ID {user_id}.")

def update_user_password(db: LLMExtractDatabase) -> None:
    """Interactively update a user's password."""
    print("\n=== Update User Password ===")

    username = input("Enter username to update: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    print(f"Found user: {username} (ID: {user['id']})")

    while True:
        new_password = getpass.getpass("Enter new password: ")
        if len(new_password) < 6:
            print("Password must be at least 6 characters long.")
            continue

        password_confirm = getpass.getpass("Confirm new password: ")
        if new_password != password_confirm:
            print("Passwords do not match.")
            continue

        break

    password_hash = get_password_hash(new_password)
    db.update_user_password(user['id'], password_hash)
    print(f"\nPassword for user '{username}' updated successfully.")

def update_user_privileges(db: LLMExtractDatabase) -> None:
    """Interactively update a user's password."""
    print("\n=== Update User Admin Privileges ===")

    username = input("Enter username to update: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    print(f"Found user: {username} (ID: {user['id']})")
    if user["is_admin"]:
        print("This user is currently an admin.")
        admin_input = input("Revoke admin privileges? (y/n): ").strip().lower()
        is_admin = admin_input not in ['y', 'yes']
    else:
        print("This user is not currently an admin.")
        admin_input = input("Grant admin privileges? (y/n): ").strip().lower()
        is_admin = admin_input in ['y', 'yes']

    if is_admin != user['is_admin']:
        db.update_user_privileges(user['id'], is_admin=is_admin)
        print(f"\nPrivileges for user '{username}' updated successfully.")

def delete_user(db: LLMExtractDatabase) -> None:
    """Interactively delete a user."""
    print("\n=== Delete User ===")

    username = input("Enter username to delete: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    print(f"Found user: {username} (ID: {user['id']})")
    print("Created at:", user['created_at'])
    print("Last login:", user.get('last_login', 'Never') or 'Never')

    confirmation = input(f"\nAre you sure you want to delete user '{username}'? (yes/no): ").strip().lower()
    if confirmation not in ['yes', 'y']:
        print("Delete operation cancelled.")
        return

    success = db.delete_user(user['id'])
    if success:
        print(f"\nUser '{username}' deleted successfully.")
    else:
        print(f"Error: Failed to delete user '{username}'.")

def list_projects(db: LLMExtractDatabase) -> None:
    """List all projects in the database."""
    projects = db.list_projects()

    if not projects:
        print("\nNo projects found in the database.")
        return

    print(f"\n{'ID':<5} {'Name':<25} {'Source Connection':<30} {'Read Only':<10} {'Created At':<25}")
    print("-" * 100)

    for project in projects:
        read_only = "Yes" if project['source_read_only'] else "No"
        print(f"{project['id']:<5} {project['name']:<25} {project['source_connection']:<30} {read_only:<10} {project['created_at']:<25}")

    print(f"\nTotal projects: {len(projects)}")

def create_new_sqlite_source(db_path: str) -> str:
    """
    Create a new SQLite source database with the standard patients/notes schema.
    Returns the SQLAlchemy connection string for the new database.
    """
    db_path = os.path.abspath(db_path)
    parent_dir = os.path.dirname(db_path)

    if not os.path.isdir(parent_dir):
        raise ValueError(f"Directory does not exist: {parent_dir}")
    if not os.access(parent_dir, os.W_OK):
        raise ValueError(f"Directory is not writable: {parent_dir}")
    if os.path.exists(db_path):
        raise ValueError(f"File already exists: {db_path}")

    connection_string = f"sqlite:///{db_path}"
    engine = sa.create_engine(connection_string)

    metadata = sa.MetaData()
    sa.Table(
        'patients', metadata,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('metadata', sa.String),
    )
    sa.Table(
        'notes', metadata,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('patient_id', sa.String),
        sa.Column('metadata', sa.String),
        sa.Column('note_text', sa.String),
        sa.Column('date', sa.String, nullable=True),
    )
    metadata.create_all(engine)
    engine.dispose()

    return connection_string


def create_project(db: LLMExtractDatabase) -> None:
    """Interactively create a new project."""
    print("\n=== Create New Project ===")

    name = input("Enter project name: ").strip()
    if not name:
        print("Project name cannot be empty.")
        return

    while True:
        source_connection = input("Enter source connection string (leave blank to create a new SQLite database): ").strip()
        if not source_connection:
            db_path = input("Enter path for new SQLite database file (e.g. databases/myproject.db): ").strip()
            if not db_path:
                print("Database path cannot be empty.")
                continue
            try:
                source_connection = create_new_sqlite_source(db_path)
                print(f"Created new source database: {source_connection}")
                break
            except ValueError as e:
                print(f"Error: {e}")
                continue

    read_only_input = input("Is source read-only? (y/n): ").strip().lower()
    source_read_only = read_only_input in ['y', 'yes']

    note_metadata_query = input("Enter note metadata query (optional): ").strip() or None
    note_text_query = input("Enter note text query (optional): ").strip() or None

    environment_vars = collect_environment_variables()

    project = Project(
        name=name,
        source_connection=source_connection,
        source_read_only=source_read_only,
        note_metadata_query=note_metadata_query,
        note_text_query=note_text_query,
        environment_vars=environment_vars
    )

    project_id = db.create_project(project)
    print(f"\nProject '{name}' created successfully with ID {project_id}.")

def update_project(db: LLMExtractDatabase) -> None:
    """Interactively update a project."""
    print("\n=== Update Project ===")

    list_projects(db)

    try:
        project_id = int(input("\nEnter project ID to update: ").strip())
    except ValueError:
        print("Invalid project ID.")
        return

    project = db.get_project_by_id(project_id)
    if not project:
        print(f"Error: Project with ID {project_id} not found.")
        return

    print(f"\nFound project: {project['name']} (ID: {project['id']})")
    print(f"Current source connection: {project['source_connection']}")
    print(f"Current read-only status: {'Yes' if project['source_read_only'] else 'No'}")

    name = input(f"Enter new name (current: {project['name']}): ").strip()
    if not name:
        name = project['name']

    source_connection = input(f"Enter new source connection (current: {project['source_connection']}): ").strip()
    if not source_connection:
        source_connection = project['source_connection']

    read_only_input = input(f"Is source read-only? (current: {'Yes' if project['source_read_only'] else 'No'}) (y/n): ").strip().lower()
    if read_only_input:
        source_read_only = read_only_input in ['y', 'yes']
    else:
        source_read_only = project['source_read_only']

    note_metadata_query = input(f"Enter note metadata query (current: {project.get('note_metadata_query', 'None')}): ").strip()
    if not note_metadata_query and note_metadata_query != "":
        note_metadata_query = project.get('note_metadata_query')
    elif note_metadata_query == "":
        note_metadata_query = None

    note_text_query = input(f"Enter note text query (current: {project.get('note_text_query', 'None')}): ").strip()
    if not note_text_query and note_text_query != "":
        note_text_query = project.get('note_text_query')
    elif note_text_query == "":
        note_text_query = None

    environment_vars = collect_environment_variables(project.get('environment_vars'))

    updated_project = Project(
        name=name,
        source_connection=source_connection,
        source_read_only=source_read_only,
        note_metadata_query=note_metadata_query,
        note_text_query=note_text_query,
        environment_vars=environment_vars
    )

    success = db.update_project(project_id, updated_project)
    if success:
        print(f"\nProject '{name}' updated successfully.")
    else:
        print(f"Error: Failed to update project.")

def delete_project(db: LLMExtractDatabase) -> None:
    """Interactively delete a project."""
    print("\n=== Delete Project ===")

    list_projects(db)

    try:
        project_id = int(input("\nEnter project ID to delete: ").strip())
    except ValueError:
        print("Invalid project ID.")
        return

    project = db.get_project_by_id(project_id)
    if not project:
        print(f"Error: Project with ID {project_id} not found.")
        return

    print(f"\nFound project: {project['name']} (ID: {project['id']})")
    print("Source connection:", project['source_connection'])
    print("Created at:", project['created_at'])

    confirmation = input(f"\nAre you sure you want to delete project '{project['name']}'? (yes/no): ").strip().lower()
    if confirmation not in ['yes', 'y']:
        print("Delete operation cancelled.")
        return

    success = db.delete_project(project_id)
    if success:
        print(f"\nProject '{project['name']}' deleted successfully.")
    else:
        print(f"Error: Failed to delete project.")

def manage_project_access(db: LLMExtractDatabase) -> None:
    """Manage user access to projects."""
    while True:
        print("\n" + "="*50)
        print("Project Access Management")
        print("="*50)
        print("1. List users in a project")
        print("2. Add user to project")
        print("3. Remove user from project")
        print("4. List projects for a user")
        print("5. Back to main menu")
        print("-" * 50)

        choice = input("Select an option (1-5): ").strip()

        if choice == '1':
            list_users_in_project(db)
        elif choice == '2':
            add_user_to_project(db)
        elif choice == '3':
            remove_user_from_project(db)
        elif choice == '4':
            list_projects_for_user(db)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please select 1-5.")

def list_users_in_project(db: LLMExtractDatabase) -> None:
    """List all users in a specific project."""
    print("\n=== List Users in Project ===")

    list_projects(db)

    try:
        project_id = int(input("\nEnter project ID: ").strip())
    except ValueError:
        print("Invalid project ID.")
        return

    project = db.get_project_by_id(project_id)
    if not project:
        print(f"Error: Project with ID {project_id} not found.")
        return

    users = db.get_users_in_project(project_id)

    if not users:
        print(f"\nNo users found in project '{project['name']}'.")
        return

    print(f"\nUsers in project '{project['name']}':")
    print(f"{'ID':<5} {'Username':<20} {'Added At':<25}")
    print("-" * 55)

    for user in users:
        print(f"{user['id']:<5} {user['username']:<20} {user['added_at']:<25}")

    print(f"\nTotal users: {len(users)}")

def add_user_to_project(db: LLMExtractDatabase) -> None:
    """Add a user to a project."""
    print("\n=== Add User to Project ===")

    list_users(db)
    username = input("\nEnter username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    list_projects(db)
    try:
        project_id = int(input("\nEnter project ID: ").strip())
    except ValueError:
        print("Invalid project ID.")
        return

    project = db.get_project_by_id(project_id)
    if not project:
        print(f"Error: Project with ID {project_id} not found.")
        return

    success = db.add_user_to_project(user['id'], project_id)
    if success:
        print(f"\nUser '{username}' added to project '{project['name']}' successfully.")
    else:
        print(f"User '{username}' is already in project '{project['name']}'.")

def remove_user_from_project(db: LLMExtractDatabase) -> None:
    """Remove a user from a project."""
    print("\n=== Remove User from Project ===")

    list_users(db)
    username = input("\nEnter username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    user_projects = db.get_user_projects(user['id'])
    if not user_projects:
        print(f"User '{username}' is not in any projects.")
        return

    print(f"\nProjects for user '{username}':")
    for i, project in enumerate(user_projects, 1):
        print(f"{i}. {project['name']} (ID: {project['id']})")

    try:
        project_choice = int(input("\nEnter project number: ").strip())
        if project_choice < 1 or project_choice > len(user_projects):
            print("Invalid project number.")
            return
        project = user_projects[project_choice - 1]
    except ValueError:
        print("Invalid project number.")
        return

    confirmation = input(f"Remove '{username}' from project '{project['name']}'? (yes/no): ").strip().lower()
    if confirmation not in ['yes', 'y']:
        print("Remove operation cancelled.")
        return

    success = db.remove_user_from_project(user['id'], project['id'])
    if success:
        print(f"\nUser '{username}' removed from project '{project['name']}' successfully.")
    else:
        print(f"Error: Failed to remove user from project.")

def list_projects_for_user(db: LLMExtractDatabase) -> None:
    """List all projects for a specific user."""
    print("\n=== List Projects for User ===")

    list_users(db)
    username = input("\nEnter username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    user = db.get_user_by_username(username)
    if not user:
        print(f"Error: User '{username}' not found.")
        return

    projects = db.get_user_projects(user['id'])

    if not projects:
        print(f"\nUser '{username}' is not in any projects.")
        return

    print(f"\nProjects for user '{username}':")
    print(f"{'ID':<5} {'Name':<25} {'Source Connection':<30}")
    print("-" * 65)

    for project in projects:
        print(f"{project['id']:<5} {project['name']:<25} {project['source_connection']:<30}")

    print(f"\nTotal projects: {len(projects)}")

def main_menu(db: LLMExtractDatabase) -> None:
    """Display the main menu and handle user input."""
    while True:
        print("\n" + "="*50)
        print("Libretto - Admin Management")
        print("="*50)
        print("User Management:")
        print("  1. List all users")
        print("  2. Create new user")
        print("  3. Update user password")
        print("  4. Update user admin privileges")
        print("  5. Delete user")
        print("Project Management:")
        print("  6. List all projects")
        print("  7. Create new project")
        print("  8. Update project")
        print("  9. Delete project")
        print("Access Management:")
        print("  10. Manage project access")
        print("General:")
        print("  11. Exit")
        print("-" * 50)

        choice = input("Select an option (1-11): ").strip()

        if choice == '1':
            list_users(db)
        elif choice == '2':
            create_user(db)
        elif choice == '3':
            update_user_password(db)
        elif choice == '4':
            update_user_privileges(db)
        elif choice == '5':
            delete_user(db)
        elif choice == '6':
            list_projects(db)
        elif choice == '7':
            create_project(db)
        elif choice == '8':
            update_project(db)
        elif choice == '9':
            delete_project(db)
        elif choice == '10':
            manage_project_access(db)
        elif choice == '11':
            print("\nExiting...")
            break
        else:
            print("Invalid choice. Please select 1-10.")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Manage Libretto users, projects, and access")
    parser.add_argument("database_url", help="SQLAlchemy database connection string")

    args = parser.parse_args()

    print(f"Connecting to database: {args.database_url}")

    try:
        db = LLMExtractDatabase(args.database_url)

        try:
            users = db.list_users()
        except Exception as e:
            print(f"Error: Database appears to be uninitialized or missing required tables.")
            print(f"Please make sure the database is properly set up and migrated.")
            print(f"Database error: {e}")
            sys.exit(1)

        print("Database connection successful!")
        main_menu(db)

    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    main()