(function () {
  "use strict";

  var orderInput = document.getElementById("order-id");
  var runBtn = document.getElementById("run-btn");
  var loading = document.getElementById("loading");
  var errorMsg = document.getElementById("error-msg");
  var results = document.getElementById("results");
  var metaBar = document.getElementById("meta-bar");
  var sessionIdEl = document.getElementById("session-id");
  var orderSection = document.getElementById("order-section");
  var orderSummary = document.getElementById("order-summary");
  var top3Grid = document.getElementById("top3-grid");
  var timeline = document.getElementById("timeline");
  var guardSection = document.getElementById("guard-section");
  var guardLogs = document.getElementById("guard-logs");

  var TOOL_LABELS = {
    query_order_detail: { title: "查看订单信息", detail: "已读取订单基本信息" },
    query_candidate_masters: { title: "筛选候选师傅", detail: "正在匹配符合条件的师傅" },
    score_master_by_rule: { title: "综合评分排序", detail: "已按距离与空闲度排序" },
    log_decision: { title: "记录推荐结果", detail: "推荐结果已保存" },
  };

  function showError(message) {
    errorMsg.textContent = message;
    errorMsg.style.display = "block";
    results.style.display = "none";
  }

  function hideError() {
    errorMsg.style.display = "none";
    errorMsg.textContent = "";
  }

  function setLoading(active) {
    runBtn.disabled = active;
    loading.style.display = active ? "block" : "none";
  }

  function makeBadge(text, className) {
    var span = document.createElement("span");
    span.className = "badge " + className;
    span.textContent = text;
    return span;
  }

  function renderMeta(data) {
    metaBar.innerHTML = "";

    metaBar.appendChild(
      makeBadge(
        data.dry_run ? "演练模式（不会真实派单）" : "联调模式",
        data.dry_run ? "badge-dry-run" : "badge-live"
      )
    );

    metaBar.appendChild(makeBadge("仅推荐，不自动派单", "badge-phase"));

    var statusClass = "badge-status";
    if (data.status === "SUCCESS") statusClass += " success";
    else if (data.status === "ESCALATED") statusClass += " escalated";

    var statusText =
      data.status_label ||
      (data.status === "SUCCESS"
        ? "推荐完成"
        : data.status === "ESCALATED"
          ? "未能完成推荐"
          : data.status);
    metaBar.appendChild(makeBadge(statusText, statusClass));

    sessionIdEl.textContent = "会话编号：" + (data.session_id || "—");
  }

  function addOrderField(container, label, value, fullWidth) {
    if (!value) return;
    var div = document.createElement("div");
    div.className = "order-field" + (fullWidth ? " full-width" : "");
    var lbl = document.createElement("label");
    lbl.textContent = label;
    var span = document.createElement("span");
    span.textContent = value;
    div.appendChild(lbl);
    div.appendChild(span);
    container.appendChild(div);
  }

  function renderOrderSummary(summary) {
    orderSummary.innerHTML = "";
    if (!summary || !summary.order_no) {
      orderSection.style.display = "none";
      return;
    }

    orderSection.style.display = "block";
    addOrderField(orderSummary, "订单号", summary.order_no);
    addOrderField(orderSummary, "业务类型", summary.biz_type_name);
    addOrderField(orderSummary, "商品类别", summary.category);
    addOrderField(orderSummary, "服务城市", summary.city);
    addOrderField(orderSummary, "客户类型", summary.customer_type);
    addOrderField(orderSummary, "服务地址", summary.address_masked, true);

    if (summary.urgent) {
      var urgentField = document.createElement("div");
      urgentField.className = "order-field";
      var lbl = document.createElement("label");
      lbl.textContent = "紧急程度";
      var span = document.createElement("span");
      span.textContent = "紧急订单";
      var tag = document.createElement("span");
      tag.className = "urgent-tag";
      tag.textContent = "加急";
      span.appendChild(tag);
      urgentField.appendChild(lbl);
      urgentField.appendChild(span);
      orderSummary.appendChild(urgentField);
    }
  }

  function renderTop3(top3) {
    top3Grid.innerHTML = "";

    if (!top3 || top3.length === 0) {
      var hint = document.createElement("p");
      hint.className = "empty-hint";
      hint.textContent = "暂未找到合适的推荐师傅";
      top3Grid.appendChild(hint);
      return;
    }

    top3.forEach(function (item, index) {
      var rankNum = item.rank || index + 1;
      var card = document.createElement("div");
      card.className = "master-card" + (rankNum === 1 ? " rank-1" : "");

      var rank = document.createElement("span");
      rank.className = "master-rank";
      rank.textContent = "第 " + rankNum + " 推荐";
      card.appendChild(rank);

      var nameEl = document.createElement("div");
      nameEl.className = "master-name";
      nameEl.textContent = item.master_name || "未知师傅";
      card.appendChild(nameEl);

      var meta = document.createElement("div");
      meta.className = "master-meta";

      var nbsRow = document.createElement("div");
      nbsRow.className = "master-meta-row";
      nbsRow.innerHTML =
        "<strong>工号：</strong>" + (item.nbs_id || "工号待补充");
      meta.appendChild(nbsRow);

      if (item.profession_type) {
        var profRow = document.createElement("div");
        profRow.className = "master-meta-row";
        profRow.innerHTML =
          "<strong>工种：</strong>" + item.profession_type;
        meta.appendChild(profRow);
      }

      if (item.service_city) {
        var cityRow = document.createElement("div");
        cityRow.className = "master-meta-row";
        cityRow.innerHTML =
          "<strong>服务城市：</strong>" + item.service_city;
        meta.appendChild(cityRow);
      }

      if (item.company_label) {
        var companyRow = document.createElement("div");
        companyRow.className = "master-meta-row";
        companyRow.innerHTML =
          "<strong>所属：</strong>" + item.company_label;
        meta.appendChild(companyRow);
      }

      card.appendChild(meta);

      var scoreRow = document.createElement("div");
      scoreRow.className = "master-score-row";
      var scoreEl = document.createElement("span");
      scoreEl.className = "master-score";
      scoreEl.textContent =
        item.score != null ? Number(item.score).toFixed(1) : "—";
      var scoreLabel = document.createElement("span");
      scoreLabel.className = "master-score-label";
      scoreLabel.textContent = "综合匹配分";
      scoreRow.appendChild(scoreEl);
      scoreRow.appendChild(scoreLabel);
      card.appendChild(scoreRow);

      var reasonBox = document.createElement("div");
      reasonBox.className = "master-reason-box";
      var reasonTitle = document.createElement("div");
      reasonTitle.className = "master-reason-title";
      reasonTitle.textContent = "推荐理由";
      var reasonEl = document.createElement("div");
      reasonEl.className = "master-reason";
      reasonEl.textContent = item.reason || "暂无详细说明";
      reasonBox.appendChild(reasonTitle);
      reasonBox.appendChild(reasonEl);
      card.appendChild(reasonBox);

      top3Grid.appendChild(card);
    });
  }

  function formatDuration(step) {
    if (step.duration_label) return step.duration_label;
    var ms = step.duration_ms != null ? step.duration_ms : 0;
    if (ms < 1000) return "用时 " + ms + " 毫秒";
    return "用时 " + (ms / 1000).toFixed(1) + " 秒";
  }

  function resolveStepLabels(step) {
    if (step.title) {
      return {
        title: step.title,
        detail: step.detail || "",
      };
    }
    var mapped = TOOL_LABELS[step.tool] || {
      title: step.tool || "处理步骤",
      detail: step.observation || "",
    };
    return mapped;
  }

  function renderTimeline(steps) {
    timeline.innerHTML = "";

    if (!steps || steps.length === 0) {
      var hint = document.createElement("p");
      hint.className = "empty-hint";
      hint.textContent = "暂无派单过程记录";
      timeline.appendChild(hint);
      return;
    }

    steps.forEach(function (step) {
      var labels = resolveStepLabels(step);
      var li = document.createElement("li");
      li.className = "timeline-item";

      var dot = document.createElement("div");
      dot.className = "timeline-dot";
      li.appendChild(dot);

      var stepLabel = document.createElement("div");
      stepLabel.className = "timeline-step";
      stepLabel.textContent = "第 " + step.step + " 步";
      li.appendChild(stepLabel);

      var titleRow = document.createElement("div");
      titleRow.className = "timeline-title";
      titleRow.textContent = labels.title;

      var dur = document.createElement("span");
      dur.className = "timeline-duration";
      dur.textContent = formatDuration(step);
      titleRow.appendChild(dur);
      li.appendChild(titleRow);

      if (labels.detail) {
        var detail = document.createElement("div");
        detail.className = "timeline-detail";
        detail.textContent = labels.detail;
        li.appendChild(detail);
      }

      timeline.appendChild(li);
    });
  }

  function renderGuardLogs(logs) {
    guardLogs.innerHTML = "";

    if (!logs || logs.length === 0) {
      guardSection.style.display = "none";
      return;
    }

    guardSection.style.display = "block";
    logs.forEach(function (entry) {
      var div = document.createElement("div");
      div.className = "guard-log";
      div.textContent =
        typeof entry === "string" ? entry : JSON.stringify(entry);
      guardLogs.appendChild(div);
    });
  }

  function renderResult(data) {
    hideError();
    results.style.display = "block";
    renderMeta(data);
    renderOrderSummary(data.order_summary);
    renderTop3(data.top3);
    renderTimeline(data.steps);
    renderGuardLogs(data.guard_logs);
  }

  async function runDispatch() {
    var orderId = orderInput.value.trim();
    if (!orderId) {
      showError("请输入订单号");
      return;
    }

    hideError();
    setLoading(true);

    try {
      var response = await fetch("/demo/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId }),
      });

      if (!response.ok) {
        var errBody = {};
        try {
          errBody = await response.json();
        } catch (_) {
          /* ignore */
        }
        var detail = errBody.detail || response.statusText || "请求失败";
        showError("派单失败 (" + response.status + "): " + detail);
        return;
      }

      var data = await response.json();
      renderResult(data);
    } catch (err) {
      showError("网络错误: " + (err.message || String(err)));
    } finally {
      setLoading(false);
    }
  }

  runBtn.addEventListener("click", runDispatch);

  orderInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !runBtn.disabled) {
      runDispatch();
    }
  });
})();
