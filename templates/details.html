<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Finance | {{ period }} Statement</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f6f9; margin: 0; padding-bottom: 50px; color: #1e293b;
        }

        /* Header */
        .header {
            display: flex; align-items: center; justify-content: space-between;
            background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(12px);
            padding: 14px 20px; position: sticky; top: 0; z-index: 100;
            border-bottom: 1px solid #e2e8f0;
        }
        .back-btn {
            text-decoration: none; color: #1e293b; font-size: 16px; font-weight: 600;
            display: flex; align-items: center; gap: 6px; background: #f1f5f9;
            padding: 8px 14px; border-radius: 20px; transition: 0.2s;
        }
        .back-btn:hover { background: #e2e8f0; }
        .header-title { font-size: 18px; font-weight: 700; margin: 0; }

        .container { max-width: 850px; margin: 20px auto; padding: 0 15px; }

        /* Bank Style Balance Card */
        .balance-card {
            background: linear-gradient(135deg, #0f172a, #1e293b);
            color: white; border-radius: 22px; padding: 24px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18); margin-bottom: 20px;
        }
        .balance-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1.2px; color: #94a3b8; margin: 0 0 6px 0; font-weight: 600; }
        .net-balance { font-size: 32px; font-weight: 800; margin: 0 0 20px 0; display: flex; align-items: center; gap: 8px; }
        
        .summary-row {
            display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
            background: rgba(255, 255, 255, 0.08); padding: 14px; border-radius: 16px;
        }
        .summary-box { display: flex; align-items: center; gap: 10px; }
        .summary-icon {
            width: 38px; height: 38px; border-radius: 12px; display: flex;
            align-items: center; justify-content: center; font-size: 18px; font-weight: bold;
        }
        .income-icon { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .expense-icon { background: rgba(244, 63, 94, 0.2); color: #fb7185; }
        .summary-info p { margin: 0; font-size: 11px; color: #cbd5e1; }
        .summary-info h4 { margin: 3px 0 0 0; font-size: 16px; font-weight: 700; }
        .income-text { color: #4ade80; }
        .expense-text { color: #fb7185; }

        /* Search & Filter Section */
        .controls-box {
            display: flex; flex-direction: column; gap: 10px; margin-bottom: 18px;
        }
        .search-wrapper {
            position: relative; display: flex; align-items: center;
        }
        .search-icon {
            position: absolute; left: 15px; color: #64748b; font-size: 16px;
        }
        .search-input {
            width: 100%; padding: 13px 15px 13px 42px; border-radius: 14px;
            border: 1px solid #cbd5e1; font-size: 15px; outline: none;
            background: white; box-sizing: border-box; transition: 0.2s;
            box-shadow: 0 2px 6px rgba(0,0,0,0.02);
        }
        .search-input:focus { border-color: #0f172a; box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.1); }

        .filter-tabs { display: flex; gap: 8px; }
        .tab-btn {
            flex: 1; padding: 10px; border-radius: 12px; border: 1px solid #e2e8f0;
            background: white; font-size: 13px; font-weight: 600; color: #64748b;
            cursor: pointer; transition: 0.2s;
        }
        .tab-btn.active { background: #0f172a; color: white; border-color: #0f172a; }

        /* Balance Sheet / Statement Table */
        .sheet-card {
            background: white; border-radius: 18px; overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;
        }
        .sheet-header {
            padding: 15px 18px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
            display: flex; justify-content: space-between; align-items: center;
        }
        .sheet-header h3 { margin: 0; font-size: 15px; font-weight: 700; color: #334155; }
        .record-count { font-size: 12px; color: #64748b; font-weight: 600; }

        .table-responsive { width: 100%; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th {
            background: #f8fafc; padding: 12px 16px; font-size: 11px;
            font-weight: 700; color: #64748b; text-transform: uppercase;
            letter-spacing: 0.8px; border-bottom: 1px solid #e2e8f0;
        }
        td {
            padding: 14px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px;
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover { background-color: #f8fafc; }

        .cat-name { font-weight: 700; color: #1e293b; display: block; margin-bottom: 3px; }
        .date-sub { font-size: 11px; color: #94a3b8; }

        .badge {
            display: inline-block; padding: 4px 9px; border-radius: 6px;
            font-size: 11px; font-weight: 700; text-transform: uppercase;
        }
        .badge-credit { background: #dcfce7; color: #15803d; }
        .badge-debit { background: #ffe4e6; color: #be123c; }

        .amt-cell { font-weight: 800; font-size: 15px; text-align: right; white-space: nowrap; }
        .amt-credit { color: #16a34a; }
        .amt-debit { color: #e11d48; }

        .empty-state {
            text-align: center; padding: 40px 20px; color: #94a3b8; font-size: 14px;
        }
    </style>
</head>
<body>

    <!-- Top Header -->
    <div class="header">
        <a href="/dashboard" class="back-btn">← Back</a>
        <h2 class="header-title">{{ period }} Balance Sheet</h2>
        <div style="width: 65px;"></div>
    </div>

    <div class="container">
        <!-- Net Balance & Account Summary Card -->
        <div class="balance-card">
            <p class="balance-label">{{ period }} Net Balance</p>
            <h1 class="net-balance">
                <span>₹</span>
                <span>{{ balance|int }}</span>
            </h1>

            <div class="summary-row">
                <div class="summary-box">
                    <div class="summary-icon income-icon">↓</div>
                    <div class="summary-info">
                        <p>Total Income (Credit)</p>
                        <h4 class="income-text">+ ₹{{ total_income|int }}</h4>
                    </div>
                </div>
                <div class="summary-box">
                    <div class="summary-icon expense-icon">↑</div>
                    <div class="summary-info">
                        <p>Total Expense (Debit)</p>
                        <h4 class="expense-text">- ₹{{ total_expense|int }}</h4>
                    </div>
                </div>
            </div>
        </div>

        <!-- Search Bar & Filter Tabs -->
        <div class="controls-box">
            <div class="search-wrapper">
                <span class="search-icon">🔍</span>
                <input type="text" id="searchInput" class="search-input" placeholder="Search category, item, or date..." onkeyup="filterTransactions()">
            </div>
            <div class="filter-tabs">
                <button class="tab-btn active" onclick="setFilter('all', this)">All Entries</button>
                <button class="tab-btn" onclick="setFilter('income', this)">Income (+)</button>
                <button class="tab-btn" onclick="setFilter('expense', this)">Expense (-)</button>
            </div>
        </div>

        <!-- Balance Sheet Statement Table -->
        <div class="sheet-card">
            <div class="sheet-header">
                <h3>Account Ledger</h3>
                <span class="record-count" id="recordCount">{{ expenses|length }} Transactions</span>
            </div>

            <div class="table-responsive">
                {% if expenses %}
                <table id="ledgerTable">
                    <thead>
                        <tr>
                            <th>Particulars & Date</th>
                            <th>Type</th>
                            <th style="text-align: right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in expenses %}
                        {% set tx_type = item.get('type', 'expense') %}
                        <tr class="tx-row" data-type="{{ tx_type }}">
                            <td>
                                <span class="cat-name">{{ item.category }}</span>
                                <span class="date-sub">{{ item.date_str }}</span>
                            </td>
                            <td>
                                {% if tx_type == 'income' %}
                                    <span class="badge badge-credit">Credit (In)</span>
                                {% else %}
                                    <span class="badge badge-debit">Debit (Out)</span>
                                {% endif %}
                            </td>
                            <td class="amt-cell {% if tx_type == 'income' %}amt-credit{% else %}amt-debit{% endif %}">
                                {% if tx_type == 'income' %}+{% else %}-{% endif %} ₹{{ item.amount|int }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <div id="noMatchMsg" class="empty-state" style="display: none;">
                    No matching transactions found.
                </div>
                {% else %}
                <div class="empty-state">
                    📭 No transactions recorded for this period yet.
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';

        function setFilter(type, btnElement) {
            currentFilter = type;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');
            filterTransactions();
        }

        function filterTransactions() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const rows = document.querySelectorAll('.tx-row');
            let visibleCount = 0;

            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                const rowType = row.getAttribute('data-type');

                const matchesSearch = text.includes(query);
                const matchesTab = (currentFilter === 'all') || (rowType === currentFilter);

                if (matchesSearch && matchesTab) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            const countEl = document.getElementById('recordCount');
            if (countEl) countEl.innerText = `${visibleCount} Transactions`;

            const noMatch = document.getElementById('noMatchMsg');
            if (noMatch) {
                noMatch.style.display = (visibleCount === 0 && rows.length > 0) ? 'block' : 'none';
            }
        }
    </script>
</body>
</html>
