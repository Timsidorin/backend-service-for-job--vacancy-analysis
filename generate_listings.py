import os

def generate_diploma_listings(root_dir, output_file):
    exclude_dirs = {'.venv', 'venv', '.git', '__pycache__', '.idea', 'build', 'docs'}
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("ПРИЛОЖЕНИЕ А\n")
        outfile.write("ЛИСТИНГИ ПРОГРАММНОГО КОДА\n\n")
        
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Фильтруем ненужные директории
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            
            for file in filenames:
                if file.endswith('.py'):
                    filepath = os.path.join(dirpath, file)
                    rel_path = os.path.relpath(filepath, root_dir)
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            content = infile.read().strip()
                            
                            # Пропускаем пустые файлы (обычно __init__.py)
                            if not content:
                                continue
                                
                            outfile.write(f"=== Файл: {rel_path} ===\n\n")
                            outfile.write(content)
                            outfile.write("\n\n" + "="*50 + "\n\n")
                    except Exception as e:
                        print(f"Ошибка при чтении {filepath}: {e}")

if __name__ == '__main__':
    project_root = r"c:\Users\timsidorin\PycharmProjects\backend-service-for-job--vacancy-analysis"
    output_path = os.path.join(project_root, "diploma_listings_full.txt")
    generate_diploma_listings(project_root, output_path)
    print(f"Успешно создано: {output_path}")
