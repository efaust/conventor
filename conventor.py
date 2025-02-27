import re
import yaml
import prettytable
import logging
from docutils.core import publish_file

from typing import Dict, List, Optional

from pathlib import Path

logger = logging.getLogger(__name__)


class Conventor:
    macros: Dict[str, str]
    sections: List[Dict[str, str]]

    tables: Dict[str, Optional[Dict[str, str]]]

    def __init__(self, input_path: Path):
        input_data = yaml.safe_load(open(input_path))

        include = input_data.pop("include")
        for i in include:
            i_path = (input_path.parent / i).resolve()
            if i_path.suffix != ".yaml":
                logger.warning(
                    f"Cowardly refusing to include content for file {i} "
                    + "it doesn't appear to be a YAML file!"
                )

            if input_path.parent.resolve() not in i_path.parents:
                logger.warning(
                    f"Cowardly refusing to include content for file {i} "
                    + "it appears to escape the parent directory!"
                )
                continue

            included_data = yaml.safe_load(open(i_path))

            input_data.update(
                {
                    (i_path.stem + "/" + key): value
                    for key, value in included_data.items()
                }
            )

        self.macros = input_data.pop("macros")
        self.sections = input_data.pop("sections")
        self.tables = input_data

    def process(self, output_dir: Path):
        for table, contents in self.tables.items():
            if table == "index":
                logger.warning(
                    "Skipping table named index, as it "
                    + "would be overwritten anyway!"
                )
                continue

            rst_table_path = output_dir / f"{table}.rst"

            # Make sure output path is safe
            if output_dir.resolve() not in rst_table_path.resolve().parents:
                logger.warning(
                    f"Cowardly refusing to write content for table {table} "
                    + "it appears to escape the parent directory!"
                )

            rst_table_path.parent.mkdir(parents=True, exist_ok=True)
            rst_table_path.write_text(self.get_rst_table(table, contents))

        # Generate index.rst
        (output_dir / "index.rst").write_text(self.get_index_rst())

        publish_file(
            source_path=str(output_dir / "index.rst"),
            destination_path=str(output_dir / "index.html"),
            writer_name="html",
        )

    def get_rst_table(self, name: str, contents: Optional[Dict[str, str]]) -> str:
        if not contents:
            return f"\n**Table <{name}> has no entries**\n"

        table = prettytable.PrettyTable()
        table.header = False
        table.hrules = prettytable.ALL
        table.field_names = ["a", "b"]
        table.align["a"] = "l"
        table.align["b"] = "l"

        all_keys = contents.keys()

        if contents.get("__re-sort__", False):
            all_keys = sorted(all_keys, key=lambda key: re.sub("[\W_]+", "", key))

        for key in all_keys:
            if key == "__re-sort__":
                continue

            left = key
            right = contents.get(key)

            table.add_row(
                [
                    self.macro_substitute(left, "left"),
                    self.macro_substitute(right, "right"),
                ]
            )

        table_contents = f".. table::\n    :widths: auto\n\n"

        for row in table.get_string().split("\n"):
            table_contents += f"    {row}\n"

        return table_contents

    def get_index_rst(self) -> str:
        output = ""

        for section in self.sections:
            title = section.get("title")
            anchor = section.get("anchor")
            contents = section.get("contents")
            hidden = section.get("hidden", False)

            if title is None or contents is None:
                logger.warning("Empty section found!")
                continue

            title = self.macro_substitute(title, "title")
            contents = self.macro_substitute(contents, "contents")

            max_line_length = max(map(len, title.split("\n")))

            if not hidden:
                output += "\n"

                if anchor:
                    output += f".. _{anchor}:"
                    output += "\n\n"

                output += "-" * max_line_length
                output += "\n"
                output += title
                output += "\n"
                output += "-" * max_line_length
                output += "\n\n"

            output += contents

        return output

    def macro_substitute(self, content: str, section: str) -> str:
        macros_to_process = {
            **self.macros["everywhere"],
            **self.macros.get(section, {}),
        }
        # TODO: Compile these ahead of time for performance
        for find, replace in macros_to_process.items():
            content = re.sub(find, replace, content)

        return content
