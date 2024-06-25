import json
from typing import Generator

import matplotlib.pyplot as plt
import networkx as nx
from nltk.tokenize import BlanklineTokenizer, word_tokenize
from pydantic import BaseModel
from typing_extensions import Literal

from biagent.utils.output_parser import json_indent_limit


class ToolMetadata(BaseModel):
    tool_name: str | None
    version: str | None
    description: str | None
    parameters: dict | None


class CellTypeToolMetadata(ToolMetadata):
    analyzed_cell_types: list[str] | None


class PipelineNode(BaseModel):
    id: int
    dep: list[int]
    name: str
    type: Literal["input", "output", "process", "cell_type_process"]
    optional: bool
    tool_required: bool
    metadata: dict


class ParagraphRotator:
    def __init__(self, paper_content: str, min_word_limit: int = None):
        paragraphs = [p.strip() for p in BlanklineTokenizer().tokenize(paper_content)]
        if min_word_limit is None:
            self.paragraphs = paragraphs
        else:
            self.paragraphs = []
            cur_p = ""
            for i, p in enumerate(paragraphs):
                cur_p += "\n\n" + p if len(cur_p) > 0 else p
                if (
                    len(word_tokenize(cur_p)) > min_word_limit
                    or i == len(paragraphs) - 1
                ):
                    self.paragraphs.append(cur_p)
                    cur_p = ""

        self.index = 0

    def get(self):
        return self.paragraphs[self.index]

    def __len__(self):
        return len(self.paragraphs)

    def __next__(self):
        to_return = self.paragraphs[self.index]
        self.step()
        return to_return

    def step(self):
        self.index += 1
        # if self.index >= len(self.paragraphs):
        #     self.index = 0

    def has_next(self):
        return self.index < len(self.paragraphs)


class Pipeline:
    def __init__(
        self, pipeline_definition: str = "data/sc_rna_seq_pipeline.json"
    ) -> None:
        self.G = self._create_graph_from_json(pipeline_definition)

    def iter_nodes(self) -> Generator[PipelineNode, None, None]:
        for node in nx.bfs_tree(self.G, 1).nodes:
            yield PipelineNode.model_validate(
                nx.get_node_attributes(self.G, "metadata")[node]
            )

    def predecessor_labels(self, id):
        return [
            nx.get_node_attributes(self.G, "label")[p] for p in self.G.predecessors(id)
        ]

    def successor_labels(self, id):
        return [
            nx.get_node_attributes(self.G, "label")[p] for p in self.G.successors(id)
        ]

    def set_node(self, node: PipelineNode, tool: ToolMetadata) -> None:
        nx.set_node_attributes(
            self.G,
            {
                node.id: {
                    "tool": json_indent_limit(tool.model_dump_json(indent=2)).replace(
                        "\n", "<br>"
                    ),
                    "has_tool_info": True,
                }
            },
        )

    def save(self, filename, save_as="html"):
        for layer, nodes in enumerate(nx.topological_generations(self.G)):
            # `multipartite_layout` expects the layer as a node attribute, so add the
            # numeric layer value as a node attribute
            for node in nodes:
                self.G.nodes[node]["layer"] = layer

        pos = nx.multipartite_layout(self.G, subset_key="layer")
        labels = nx.get_node_attributes(self.G, "label")
        nx.set_node_attributes(self.G, pos, "pos")
        if save_as == "png":
            plt.figure(figsize=(15, 10))
            nx.draw(
                self.G,
                pos,
                with_labels=True,
                labels=labels,
                node_color="lightblue",
                font_weight="bold",
            )
            plt.title("Directed Graph from JSON")
            if filename:
                plt.savefig(filename)
            else:
                plt.show()
        elif save_as == "html":
            assert filename and filename.endswith(".html")
            import igviz as ig

            node_colors = [
                "red" if self.G.nodes[node]["has_tool_info"] else "blue"
                for node in self.G.nodes()
            ]

            plotly_g = ig.plot(
                self.G,
                color_method=node_colors,
                node_text=["name", "tool", "has_tool_info"],
                node_label="name",
            )
            plotly_g.write_html(filename)
        elif save_as == "json":
            raise NotImplementedError

    def _create_graph_from_json(self, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)

        G = nx.DiGraph()

        # Add nodes with labels
        for node in data:
            G.add_node(
                node["id"],
                label=node["name"],
                name=node["name"],
                tool=None,
                metadata=node,
                has_tool_info=False,
            )

        # Add edges based on dependencies
        for node in data:
            for dep in node["dep"]:
                G.add_edge(dep, node["id"])

        return G
