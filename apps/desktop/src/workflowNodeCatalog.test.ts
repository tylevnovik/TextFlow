import { describe, expect, it } from "vitest";

import { builtinWorkflowNodeSchema } from "./generatedBuiltinWorkflowNodeSchema";
import {
  builtinWorkflowNodeDefinitions,
  missingBuiltinWorkflowNodeUiDefinitionsForTest
} from "./workflowNodeCatalog";

describe("workflowNodeCatalog", () => {
  it("has explicit UI defaults for every generated workflow node", () => {
    expect(missingBuiltinWorkflowNodeUiDefinitionsForTest()).toEqual([]);
  });

  it("builds frontend definitions for all generated workflow nodes", () => {
    expect(Object.keys(builtinWorkflowNodeDefinitions)).toEqual(
      expect.arrayContaining(Object.keys(builtinWorkflowNodeSchema))
    );
  });
});
