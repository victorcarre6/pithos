import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { brokerRequest } from "../lib/broker-socket.ts";

const promoteTool = (pi: ExtensionAPI) => defineTool({
  name: "pithos_promote",
  label: "Pithos Promote",
  description: "Validate and activate a staged skill, extension, prompt or instruction file.",
  parameters: Type.Object({
    kind: Type.Union([
      Type.Literal("skill"),
      Type.Literal("extension"),
      Type.Literal("prompt"),
      Type.Literal("instructions"),
    ]),
    staged: Type.String({ description: "Path below .pithos-staging" }),
    target: Type.String({ description: "Active AGENTS.md, SYSTEM.md or .pi resource path" }),
  }),

  async execute(_toolCallId, params, signal) {
    const socketPath = process.env.PITHOS_HARNESS_SOCKET;
    const runId = process.env.PITHOS_RUN_ID;
    if (!socketPath || !runId) {
      throw new Error("PITHOS_HARNESS_SOCKET and PITHOS_RUN_ID are required");
    }

    const response = await brokerRequest(
      socketPath,
      {
        run_id: runId,
        kind: params.kind,
        staged: params.staged,
        target: params.target,
      },
      signal,
    );
    if (!response.ok) {
      throw new Error(String(response.error ?? "Harness broker rejected promotion"));
    }

    pi.sendUserMessage("/pithos-reload", { deliverAs: "followUp" });

    return {
      content: [{ type: "text" as const, text: `Promoted ${String(response.target)}; reload queued.` }],
      details: response,
    };
  },
});

export default function pithosHarness(pi: ExtensionAPI) {
  pi.registerCommand("pithos-reload", {
    description: "Reload validated Pithos harness resources.",
    handler: async (_args, context) => {
      await context.reload();
    },
  });
  pi.registerTool(promoteTool(pi));
}
