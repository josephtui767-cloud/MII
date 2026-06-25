/** Enhanced Trust Graph — full map of all identities and trust relationships. */

import { useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";
import { fetchGraphStats } from "../../api/client";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 70;

interface GraphNode {
  id: string;
  name: string;
  type: string;
  source: string;
  risk_score: number;
  last_used_at: string | null;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  trust_type: string;
}

interface FullGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

function getLayoutedElements(nodes: Node[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 80, ranksep: 150 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const position = g.node(node.id);
    return {
      ...node,
      position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  return { nodes: layoutedNodes, edges };
}

function getRiskColor(score: number): string {
  if (score >= 60) return "#fecaca";
  if (score >= 35) return "#fed7aa";
  if (score >= 10) return "#fef3c7";
  return "#d1fae5";
}

function getRiskBorder(score: number): string {
  if (score >= 60) return "#ef4444";
  if (score >= 35) return "#f97316";
  if (score >= 10) return "#eab308";
  return "#10b981";
}

function getTypeIcon(type: string): string {
  if (type === "GitLab_Runner") return "🔶";
  if (type === "AWS_IAM_Role") return "☁️";
  if (type === "GitLab_Project_Access_Token") return "🔑";
  return "🔹";
}

export function TrustGraphView() {
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const { data: graphStats } = useQuery({
    queryKey: ["graph-stats"],
    queryFn: fetchGraphStats,
  });

  const { data: fullGraph, isLoading } = useQuery<FullGraphResponse>({
    queryKey: ["graph-full"],
    queryFn: async () => {
      const { data } = await api.get("/graph/full");
      return data;
    },
  });

  // Build React Flow nodes/edges from full graph data
  useEffect(() => {
    if (!fullGraph) return;

    const flowNodes: Node[] = fullGraph.nodes.map((node) => ({
      id: node.id,
      data: {
        label: (
          <div className="text-center">
            <div className="text-xs font-semibold truncate">
              {getTypeIcon(node.type)} {node.name}
            </div>
            <div className="text-[10px] text-gray-500 mt-0.5">
              {node.type.replace(/_/g, " ")} | Risk: {node.risk_score}
            </div>
          </div>
        ),
      },
      position: { x: 0, y: 0 },
      style: {
        background: getRiskColor(node.risk_score),
        border: `2px solid ${getRiskBorder(node.risk_score)}`,
        borderRadius: 10,
        padding: "10px 14px",
        fontSize: 12,
        width: NODE_WIDTH,
        cursor: "pointer",
      },
    }));

    const flowEdges: Edge[] = fullGraph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.trust_type.replace(/_/g, " "),
      labelStyle: { fontSize: 10, fontWeight: 600 },
      style: {
        strokeWidth: 2,
        stroke: edge.trust_type === "OIDC_Federation" ? "#8b5cf6" :
                edge.trust_type === "Cross_Account_Trust" ? "#ef4444" :
                edge.trust_type === "AssumeRole" ? "#3b82f6" : "#6b7280",
      },
      animated: edge.trust_type === "OIDC_Federation",
      type: "smoothstep",
    }));

    // Only layout nodes that have edges (connected nodes)
    const connectedNodeIds = new Set<string>();
    flowEdges.forEach((e) => {
      connectedNodeIds.add(e.source);
      connectedNodeIds.add(e.target);
    });

    // Show connected nodes prominently, disconnected nodes in a separate area
    const connectedNodes = flowNodes.filter((n) => connectedNodeIds.has(n.id));
    const disconnectedNodes = flowNodes.filter((n) => !connectedNodeIds.has(n.id));

    // Layout connected nodes with dagre
    const { nodes: layoutedConnected, edges: layoutedEdges } = getLayoutedElements(connectedNodes, flowEdges);

    // Position disconnected nodes in a grid below
    const startY = layoutedConnected.length > 0
      ? Math.max(...layoutedConnected.map((n) => n.position.y)) + 200
      : 0;

    const layoutedDisconnected = disconnectedNodes.map((node, idx) => ({
      ...node,
      position: {
        x: (idx % 4) * (NODE_WIDTH + 40),
        y: startY + Math.floor(idx / 4) * (NODE_HEIGHT + 40),
      },
    }));

    setNodes([...layoutedConnected, ...layoutedDisconnected]);
    setEdges(layoutedEdges);
  }, [fullGraph, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      navigate(`/identity/${node.id}`);
    },
    [navigate]
  );

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Trust Graph</h2>
          <p className="text-sm text-gray-500 mt-1">
            Full map of all machine identities and trust relationships. Click any node to view details and AI remediation.
          </p>
          {graphStats && (
            <p className="text-xs text-gray-400 mt-1">
              {graphStats.node_count} identities, {graphStats.edge_count} trust relationships, {graphStats.connected_components} groups
            </p>
          )}
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-1 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-purple-500 rounded" /> OIDC Federation
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-red-500 rounded" /> Cross Account
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-blue-500 rounded" /> AssumeRole
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded border-2 border-red-500 bg-red-100" /> High Risk
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded border-2 border-green-500 bg-green-100" /> Low Risk
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      )}

      {!isLoading && nodes.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          No identities discovered. Run a discovery scan first.
        </div>
      )}

      {nodes.length > 0 && (
        <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden" style={{ minHeight: 600 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            attributionPosition="bottom-left"
          >
            <Background />
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              nodeColor={() => "#e2e8f0"}
            />
          </ReactFlow>
        </div>
      )}
    </div>
  );
}
