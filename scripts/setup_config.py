#!/usr/bin/env python
"""
Quick configuration setup script for TranslateBookWithLLM

This script helps users create and configure their .env file.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.env_helper import (
    create_env_from_template,
    validate_env_config,
    interactive_env_setup
)


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*70)
    print("  TranslateBookWithLLM - Configuration Setup")
    print("="*70 + "\n")


def print_menu():
    """Print main menu"""
    print("What would you like to do?\n")
    print("  1. Quick setup (copy from .env.example)")
    print("  2. Interactive setup wizard (guided configuration)")
    print("  3. Validate current configuration")
    print("  4. Exit\n")


def main():
    """Main menu loop"""
    print_banner()

    while True:
        print_menu()

        try:
            choice = input("Enter your choice (1-4): ").strip()

            if choice == '1':
                print("\n📋 Quick Setup - Copying .env.example to .env...")
                if create_env_from_template():
                    print("\n✅ Success! Please edit .env to configure your settings.")
                    print("   Key settings to configure:")
                    print("   • API_ENDPOINT - Your LLM server address")
                    print("   • LLM_PROVIDER - ollama, gemini, or openai")
                    print("   • DEFAULT_MODEL - Model name to use")
                    print("\n   After editing, run option 3 to validate.\n")
                else:
                    print("\n❌ Quick setup failed. Try option 2 for interactive setup.\n")

            elif choice == '2':
                interactive_env_setup()
                print("\n✅ Setup complete! Run option 3 to validate.\n")

            elif choice == '3':
                print("\n🔍 Validating configuration...")
                status = validate_env_config(verbose=True)

                if status['issues']:
                    print("❌ Please fix the issues above before starting the application.\n")
                elif status['warnings']:
                    print("⚠️  Configuration has warnings but should work.\n")
                else:
                    print("✅ Configuration is ready! You can start the application.\n")

            elif choice == '4':
                print("\n👋 Goodbye!\n")
                break

            else:
                print("\n❌ Invalid choice. Please enter 1, 2, 3, or 4.\n")

        except KeyboardInterrupt:
            print("\n\n👋 Setup cancelled. Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == '__main__':
    main()
