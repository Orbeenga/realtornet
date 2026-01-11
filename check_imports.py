# check_imports.py
"""
Import validator for FastAPI project.
Scans CRUD and Models for missing or incorrect imports.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

class ImportScanner:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.models_dir = self.project_root / "app" / "models"
        self.crud_dir = self.project_root / "app" / "crud"
        self.schemas_dir = self.project_root / "app" / "schemas"
        
        # Store available models
        self.available_models: Dict[str, str] = {}  # {ModelName: file_path}
        self.issues: List[str] = []
    
    def scan_available_models(self):
        """Scan models directory to find all available model classes."""
        print("🔍 Scanning available models...")
        
        for file_path in self.models_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find class definitions
            class_pattern = r'^class\s+(\w+)\s*\([^)]*Base[^)]*\):'
            matches = re.finditer(class_pattern, content, re.MULTILINE)
            
            for match in matches:
                class_name = match.group(1)
                self.available_models[class_name] = file_path.name
                print(f"  ✓ Found {class_name} in {file_path.name}")
        
        # Also scan for Table objects (junction tables)
        for file_path in self.models_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find Table definitions
            table_pattern = r'^(\w+)\s*=\s*Table\s*\('
            matches = re.finditer(table_pattern, content, re.MULTILINE)
            
            for match in matches:
                table_name = match.group(1)
                self.available_models[table_name] = file_path.name
                print(f"  ✓ Found Table '{table_name}' in {file_path.name}")
        
        print(f"\n📊 Total models found: {len(self.available_models)}\n")
    
    def extract_imports_from_file(self, file_path: Path) -> List[Tuple[str, str, int]]:
        """Extract model imports from a file."""
        imports = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            # Match: from app.models.xxx import YYY
            match = re.match(r'from\s+app\.models\.(\w+)\s+import\s+(.+)', line)
            if match:
                source_file = match.group(1) + ".py"
                imports_str = match.group(2)
                
                # Handle multiple imports: User, Agency, etc.
                imported_items = [item.strip() for item in imports_str.split(',')]
                
                for item in imported_items:
                    # Remove 'as' aliases
                    item = item.split(' as ')[0].strip()
                    imports.append((item, source_file, line_num))
            
            # Match: from app.models import YYY (shortcut)
            match = re.match(r'from\s+app\.models\s+import\s+(.+)', line)
            if match:
                imports_str = match.group(1)
                imported_items = [item.strip() for item in imports_str.split(',')]
                
                for item in imported_items:
                    item = item.split(' as ')[0].strip()
                    imports.append((item, "__init__.py", line_num))
        
        return imports
    
    def validate_crud_imports(self):
        """Check CRUD files for incorrect model imports."""
        print("🔍 Validating CRUD imports...\n")
        
        for file_path in self.crud_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            print(f"📄 Checking {file_path.name}...")
            imports = self.extract_imports_from_file(file_path)
            
            for model_name, source_file, line_num in imports:
                if model_name not in self.available_models:
                    issue = f"  ❌ Line {line_num}: '{model_name}' not found in any model file"
                    print(issue)
                    self.issues.append(f"{file_path.name}: {issue}")
                elif source_file != "__init__.py":
                    # Check if importing from correct file
                    correct_file = self.available_models[model_name]
                    if source_file != correct_file:
                        issue = f"  ⚠️  Line {line_num}: '{model_name}' imported from '{source_file}' but exists in '{correct_file}'"
                        print(issue)
                        self.issues.append(f"{file_path.name}: {issue}")
                    else:
                        print(f"  ✓ Line {line_num}: '{model_name}' from '{source_file}' - OK")
            
            if not imports:
                print("  ℹ️  No model imports found")
            print()
    
    def validate_schema_imports(self):
        """Check schema files for incorrect model/enum imports."""
        print("🔍 Validating Schema imports...\n")
        
        if not self.schemas_dir.exists():
            print("  ℹ️  Schemas directory not found, skipping\n")
            return
        
        for file_path in self.schemas_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            print(f"📄 Checking {file_path.name}...")
            imports = self.extract_imports_from_file(file_path)
            
            for model_name, source_file, line_num in imports:
                if model_name not in self.available_models:
                    # Might be an enum, check if it exists
                    issue = f"  ⚠️  Line {line_num}: '{model_name}' not found (might be enum - verify manually)"
                    print(issue)
                elif source_file != "__init__.py":
                    correct_file = self.available_models[model_name]
                    if source_file != correct_file:
                        issue = f"  ⚠️  Line {line_num}: '{model_name}' imported from '{source_file}' but exists in '{correct_file}'"
                        print(issue)
                        self.issues.append(f"{file_path.name}: {issue}")
                    else:
                        print(f"  ✓ Line {line_num}: '{model_name}' from '{source_file}' - OK")
            
            if not imports:
                print("  ℹ️  No model imports found")
            print()
    
    def check_circular_imports(self):
        """Check for potential circular import issues."""
        print("🔍 Checking for circular import risks...\n")
        
        # Check if models/__init__.py imports everything
        init_file = self.models_dir / "__init__.py"
        if init_file.exists():
            with open(init_file, 'r') as f:
                content = f.read()
            
            # Check if any model file tries to import from package level
            for file_path in self.models_dir.glob("*.py"):
                if file_path.name.startswith("_"):
                    continue
                
                with open(file_path, 'r') as f:
                    file_content = f.read()
                
                if re.search(r'from\s+app\.models\s+import', file_content):
                    issue = f"  ⚠️  {file_path.name} uses package-level import - potential circular import risk!"
                    print(issue)
                    self.issues.append(issue)
        
        print()
    
    def generate_report(self):
        """Generate final report."""
        print("=" * 70)
        print("📋 FINAL REPORT")
        print("=" * 70)
        
        if not self.issues:
            print("✅ No import issues found! All imports are correct.")
        else:
            print(f"⚠️  Found {len(self.issues)} potential issues:\n")
            for issue in self.issues:
                print(f"  • {issue}")
        
        print("\n" + "=" * 70)
    
    def run(self):
        """Run all checks."""
        print("=" * 70)
        print("🚀 IMPORT VALIDATOR - FastAPI Project")
        print("=" * 70)
        print()
        
        self.scan_available_models()
        self.validate_crud_imports()
        self.validate_schema_imports()
        self.check_circular_imports()
        self.generate_report()


if __name__ == "__main__":
    scanner = ImportScanner()
    scanner.run()