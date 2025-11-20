"""Intent routing with Chain-of-Thought decision making"""

ROUTER_PROMPT = """Analyze user query and route to correct handler.

## ROUTING LOGIC:
Step 1: Identify primary financial topic
Step 2: Match to category keywords
Step 3: If unclear, default to relevant option

## CATEGORIES & KEYWORDS:

**GOLD** Route: Precious metals queries
- Keywords: vàng, gold, sjc, doji, pnj, kim loại, bullion, precious metals, giá vàng
- Example: "What's the gold price?" → GOLD

**STOCK** Route: Equity markets
- Keywords: chứng khoán, cổ phiếu, stock, share, vnindex, nasdaq, dow, index, thị trường chứng khoán, trading
- Example: "How's VCB today?" → STOCK

**NEWS** Route: Market news & analysis
- Keywords: tin tức, news, sự kiện, breaking news, market analysis, earnings, thị trường, events
- Example: "Any financial news today?" → NEWS

**DEFAULT** Route: Non-financial queries
- Everything else: weather, sports, general knowledge
- Example: "What's the capital of Vietnam?" → DEFAULT

## USER QUERY:
{input}

## ANALYSIS:
1. Identify main topic
2. Match keywords
3. Determine best route

## RESPONSE FORMAT:
destination: [gold|stock|news|default]"""
