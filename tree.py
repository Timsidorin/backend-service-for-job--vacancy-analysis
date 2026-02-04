import sys
from pathlib import Path


def print_tree(directory: Path, prefix: str = "", current_depth: int = 0, max_depth: int = 3):
    """
    Выводит только директории (без файлов) с ограничением глубины.
    """
    # Если достигли лимита глубины, останавливаемся
    if current_depth >= max_depth:
        return

    if not directory.is_dir():
        return

    try:
        # Фильтруем: берем ТОЛЬКО папки (is_dir)
        contents = [x for x in directory.iterdir() if x.is_dir()]
        # Сортируем по имени
        contents.sort(key=lambda x: x.name.lower())
    except PermissionError:
        print(f"{prefix}└── [Доступ запрещен]")
        return

    # Если папок нет, выходим
    if not contents:
        return

    # Подготовка отрисовки (ветки)
    pointers = [("├── ", "│   ")] * (len(contents) - 1) + [("└── ", "    ")]

    for pointer, item in zip(pointers, contents):
        connector, next_prefix_extension = pointer

        # Печатаем название папки
        print(f"{prefix}{connector}{item.name}")

        # Рекурсия: заходим внутрь, если не достигли предела
        if current_depth + 1 < max_depth:
            new_prefix = prefix + next_prefix_extension
            print_tree(item, new_prefix, current_depth + 1, max_depth)


def main():
    # Путь по умолчанию - текущая папка
    path_arg = sys.argv[1] if len(sys.argv) > 1 else "."

    # Глубина по умолчанию - 3
    depth_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    root_dir = Path(path_arg)

    if not root_dir.exists():
        print(f"Ошибка: Директория '{root_dir}' не найдена.")
        return

    print(f"📁 {root_dir.resolve().name} (Только папки, Глубина: {depth_arg})")
    print_tree(root_dir, max_depth=depth_arg)


if __name__ == "__main__":
    main()
