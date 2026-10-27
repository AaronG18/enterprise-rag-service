import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Input,
  Layout,
  List,
  Popover,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message as antdMessage,
} from "antd";
import {
  ApiOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

const { Header, Content, Footer } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

type Retrieved = {
  chunk_id: string;
  doc_id: string;
  section: string;
  language: string;
  ocr: boolean;
  text: string;
  fused_score: number;
};

type Answer = {
  text: string;
  citations: string[];
  refused: boolean;
  reason_code: string | null;
  guidance: string;
  confidence: number;
  usage: { total_tokens: number };
  provider: string;
  model_version: string;
};

type Turn = {
  role: "user" | "assistant";
  question?: string;
  answer?: Answer;
  retrieved?: Retrieved[];
  trace?: Record<string, unknown>;
  latency_ms?: number;
  error?: { error: string; detail?: string; hint?: string };
};

const PROVIDERS = [
  {
    id: "deterministic",
    label: "Deterministic (offline)",
    hint: "No key, no network. Answers are composed from retrieved passages.",
  },
  {
    id: "codebuddy-serve",
    label: "CodeBuddy local serve",
    hint: "Local CodeBuddy CLI serve on 127.0.0.1. Requires the serve to be running.",
  },
  {
    id: "openai-compatible",
    label: "Bring your own key",
    hint: "Any OpenAI-compatible chat-completions endpoint. The key is sent per request and never stored.",
  },
] as const;

const ERROR_TITLES: Record<string, string> = {
  bad_request: "Request incomplete",
  provider_unavailable: "Provider unavailable",
  network_error: "Network error",
  internal_error: "Server error",
};

const SAMPLE_QUESTIONS = [
  "How many days of annual leave do full-time employees accrue?",
  "How often must third-party vendors be reassessed?",
  "What is the p95 latency target of the query service?",
  "语义缓存的 TTL 是多少秒",
  "quarterly dividend policy for bitcoin miners",
];

export default function App() {
  const [provider, setProvider] = useState<string>("deterministic");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:8788");
  const [model, setModel] = useState("hy3");
  const [apiKey, setApiKey] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem("ers-session");
    if (stored) setSessionId(stored);
    else {
      const fresh = "web-" + Math.random().toString(36).slice(2, 10);
      window.localStorage.setItem("ers-session", fresh);
      setSessionId(fresh);
    }
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const activeProvider = useMemo(
    () => PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0],
    [provider]
  );

  const ask = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;
      setBusy(true);
      setTurns((prev) => [...prev, { role: "user", question: trimmed }]);
      try {
        const payload: Record<string, unknown> = {
          question: trimmed,
          session_id: sessionId || undefined,
          provider,
        };
        if (provider !== "deterministic") {
          payload.endpoint = endpoint;
          if (provider === "openai-compatible") {
            payload.api_key = apiKey;
            payload.model = model;
          } else {
            payload.model = model;
          }
        }
        const response = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (data.error) {
          setTurns((prev) => [
            ...prev,
            { role: "assistant", error: { error: data.error, detail: data.detail, hint: data.hint } },
          ]);
        } else {
          setTurns((prev) => [
            ...prev,
            {
              role: "assistant",
              answer: data.answer,
              retrieved: data.retrieved,
              trace: data.trace,
              latency_ms: data.latency_ms,
            },
          ]);
        }
      } catch (err) {
        setTurns((prev) => [
          ...prev,
          {
            role: "assistant",
            error: { error: "network_error", detail: String(err) },
          },
        ]);
      } finally {
        setBusy(false);
        setQuestion("");
      }
    },
    [apiKey, busy, endpoint, model, provider, sessionId]
  );

  const citationPopover = (chunkId: string) => {
    const chunk = turns
      .flatMap((t) => t.retrieved ?? [])
      .find((c) => c.chunk_id === chunkId);
    if (!chunk) return <span>{chunkId}</span>;
    return (
      <div style={{ maxWidth: 420 }}>
        <Space direction="vertical" size={4}>
          <Text strong>{chunk.chunk_id}</Text>
          <Text type="secondary">
            {chunk.doc_id} · {chunk.section} · {chunk.language.toUpperCase()}
            {chunk.ocr ? " · scanned" : ""}
          </Text>
          <Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>{chunk.text}</Paragraph>
        </Space>
      </div>
    );
  };

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f6f7" }}>
      <Header
        style={{
          background: "#0f6b5c",
          display: "flex",
          alignItems: "center",
          gap: 12,
          paddingInline: 24,
        }}
      >
        <ApiOutlined style={{ color: "#fff", fontSize: 20 }} />
        <Title level={4} style={{ color: "#fff", margin: 0, flex: 1 }}>
          Enterprise RAG Service
        </Title>
        <Badge
          status={health ? "success" : "error"}
          text={
            <span style={{ color: "#fff" }}>
              {health
                ? `corpus ${String(health.corpus_version)} · ${String(health.chunks)} chunks`
                : "api unreachable"}
            </span>
          }
        />
      </Header>

      <Content style={{ padding: 24, maxWidth: 1080, margin: "0 auto", width: "100%" }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card
              title={
                <Space>
                  <MessageOutlined />
                  <span>Conversation</span>
                </Space>
              }
              extra={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  session {sessionId || "-"}
                </Text>
              }
              styles={{ body: { padding: 0 } }}
            >
              <div
                ref={listRef}
                style={{ maxHeight: "52vh", overflowY: "auto", padding: 16 }}
              >
                <List
                  itemLayout="vertical"
                  dataSource={turns}
                  locale={{ emptyText: "Ask a question, or pick one of the samples below." }}
                  renderItem={(turn, index) => (
                    <List.Item key={index} style={{ borderBottom: "none" }}>
                      {turn.role === "user" ? (
                        <Card
                          size="small"
                          style={{ background: "#eef7f5", border: "none", marginLeft: 48 }}
                        >
                          <Text strong>{turn.question}</Text>
                        </Card>
                      ) : turn.error ? (
                        <Alert
                          type="warning"
                          showIcon
                          message={ERROR_TITLES[turn.error.error] ?? turn.error.error}
                          description={
                            <Space direction="vertical" size={4}>
                              {turn.error.detail ? <Text>{turn.error.detail}</Text> : null}
                              {turn.error.hint ? <Text type="secondary">{turn.error.hint}</Text> : null}
                            </Space>
                          }
                          style={{ marginRight: 48 }}
                        />
                      ) : (
                        <Card
                          size="small"
                          style={{ marginRight: 48 }}
                          title={
                            <Space size={8}>
                              <SafetyCertificateOutlined style={{ color: "#0f6b5c" }} />
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {turn.answer?.provider} · {turn.answer?.model_version}
                              </Text>
                              <Tag color="blue">{turn.latency_ms} ms</Tag>
                              <Tag>{turn.answer?.usage.total_tokens} tokens (est.)</Tag>
                            </Space>
                          }
                          extra={
                            <Tag color={turn.answer?.refused ? "orange" : "green"}>
                              {turn.answer?.refused ? turn.answer?.reason_code : "answered"}
                            </Tag>
                          }
                        >
                          {turn.answer?.refused ? (
                            <Alert
                              type="info"
                              showIcon
                              message="Refused"
                              description={turn.answer.guidance}
                            />
                          ) : (
                            <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 12 }}>
                              {turn.answer?.text}
                            </Paragraph>
                          )}

                          <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
                            {(turn.answer?.citations ?? []).map((cid) => (
                              <Popover key={cid} content={citationPopover(cid)} title="Cited passage">
                                <Tag style={{ cursor: "pointer" }}>{cid}</Tag>
                              </Popover>
                            ))}
                          </Space>

                          <Collapse
                            ghost
                            size="small"
                            items={[
                              {
                                key: "trace",
                                label: (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    trace &amp; retrieved passages
                                  </Text>
                                ),
                                children: (
                                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                    <Descriptions
                                      size="small"
                                      bordered
                                      column={2}
                                      items={[
                                        {
                                          label: "confidence",
                                          children: String(turn.trace?.confidence ?? "-"),
                                        },
                                        {
                                          label: "coverage",
                                          children: String(turn.trace?.coverage ?? "-"),
                                        },
                                        {
                                          label: "retrieval",
                                          children: `${String(turn.trace?.retrieval_mode ?? "-")}${
                                            turn.trace?.rerank_enabled ? " + rerank" : ""
                                          }`,
                                        },
                                        {
                                          label: "citation source",
                                          children: String(turn.trace?.citation_source ?? "n/a"),
                                        },
                                        {
                                          label: "query rewritten",
                                          children: String(turn.trace?.query_rewritten ?? false),
                                        },
                                        {
                                          label: "cache hit",
                                          children: String(turn.trace?.cache_hit ?? false),
                                        },
                                      ]}
                                    />
                                    <List
                                      size="small"
                                      dataSource={turn.retrieved ?? []}
                                      renderItem={(chunk) => (
                                        <List.Item>
                                          <List.Item.Meta
                                            title={
                                              <Space size={6}>
                                                <Text code style={{ fontSize: 12 }}>
                                                  {chunk.chunk_id}
                                                </Text>
                                                <Text type="secondary" style={{ fontSize: 12 }}>
                                                  {chunk.section}
                                                </Text>
                                                {chunk.ocr ? <Tag color="orange">scanned</Tag> : null}
                                              </Space>
                                            }
                                            description={
                                              <Text type="secondary" style={{ fontSize: 12 }}>
                                                {chunk.text.slice(0, 160)}
                                                {chunk.text.length > 160 ? "..." : ""}
                                              </Text>
                                            }
                                          />
                                        </List.Item>
                                      )}
                                    />
                                  </Space>
                                ),
                              },
                            ]}
                          />
                        </Card>
                      )}
                    </List.Item>
                  )}
                />
                {busy ? (
                  <div style={{ textAlign: "center", padding: 16 }}>
                    <Spin tip="retrieving and generating" />
                  </div>
                ) : null}
              </div>

              <div style={{ borderTop: "1px solid #f0f0f0", padding: 12 }}>
                <Space.Compact style={{ width: "100%" }}>
                  <TextArea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onPressEnter={(e) => {
                      if (!e.shiftKey) {
                        e.preventDefault();
                        void ask(question);
                      }
                    }}
                    placeholder="Ask about the handbook, compliance guides, specifications or architecture documents (Enter to send, Shift+Enter for a new line)"
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    disabled={busy}
                  />
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={() => void ask(question)}
                    loading={busy}
                  >
                    Ask
                  </Button>
                </Space.Compact>
                <div style={{ marginTop: 8 }}>
                  <Space wrap size={[6, 6]}>
                    {SAMPLE_QUESTIONS.map((q) => (
                      <Button key={q} size="small" onClick={() => void ask(q)} disabled={busy}>
                        {q.length > 46 ? q.slice(0, 46) + "..." : q}
                      </Button>
                    ))}
                  </Space>
                </div>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card
              title={
                <Space>
                  <ThunderboltOutlined />
                  <span>Provider</span>
                </Space>
              }
            >
              <Segmented
                block
                value={provider}
                onChange={(value) => setProvider(String(value))}
                options={PROVIDERS.map((p) => ({ label: p.label, value: p.id }))}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12 }}>
                {activeProvider.hint}
              </Paragraph>

              {provider !== "deterministic" ? (
                <Space direction="vertical" size={12} style={{ width: "100%", marginTop: 8 }}>
                  <div>
                    <Text type="secondary">endpoint</Text>
                    <Input
                      value={endpoint}
                      onChange={(e) => setEndpoint(e.target.value)}
                      placeholder="http://127.0.0.1:8788"
                    />
                  </div>
                  <div>
                    <Text type="secondary">model</Text>
                    <Input value={model} onChange={(e) => setModel(e.target.value)} />
                  </div>
                  {provider === "openai-compatible" ? (
                    <div>
                      <Text type="secondary">api key (never stored, never logged)</Text>
                      <Input.Password
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="sk-..."
                      />
                    </div>
                  ) : null}
                </Space>
              ) : null}

              <Alert
                style={{ marginTop: 16 }}
                type="info"
                showIcon
                message="Why two lanes"
                description="The deterministic provider needs no key and is what CI verifies. A real model is optional: supply your own endpoint and the same evaluation harness scores it, tagged model-backed."
              />
            </Card>

            <Card title="How the pipeline works" style={{ marginTop: 16 }}>
              <List
                size="small"
                dataSource={[
                  "Bilingual tokenisation (CJK characters + bigrams, latin words, numbers kept)",
                  "Hybrid retrieval: hashing vectors + BM25, fused by Reciprocal Rank Fusion",
                  "Optional reranker, toggled by configuration only",
                  "Grounding: answers cite retrieved chunk ids; unsupported questions refuse",
                  "PII redaction on answers and log records",
                ]}
                renderItem={(item) => (
                  <List.Item>
                    <Text style={{ fontSize: 12 }}>{item}</Text>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        </Row>
      </Content>

      <Footer style={{ textAlign: "center", background: "#f5f6f7" }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          stdlib-only backend · no database · deterministic corpus · every number carries a
          provenance tag
        </Text>
      </Footer>
    </Layout>
  );
}
