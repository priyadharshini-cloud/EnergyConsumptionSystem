// ============================================================
// VOLTPULSE &bull; SMART ELECTRICITY ENERGY & BILL PREDICTION PLATFORM
// Real-time Meter Tracking &bull; Progressive Slabs &bull; Scikit-Learn Forecasting
// ============================================================

document.addEventListener("DOMContentLoaded", function () {
  // Global State & Chart instances
  let currentDashboardData = null;
  let forecastChartInstance = null;
  let dailyTrendChartInstance = null;
  let monthCompareChartInstance = null;
  let allReadingsList = [];

  // DOM Elements
  const readingDateInput = document.getElementById("readingDate");
  const meterApplianceInput = document.getElementById("meterAppliance");
  const prevReadingInput = document.getElementById("prevReading");
  const currReadingInput = document.getElementById("currReading");
  const previewKwh = document.getElementById("previewKwh");
  const previewCost = document.getElementById("previewCost");
  const mathEquation = document.getElementById("mathEquation");
  const meterForm = document.getElementById("meterForm");
  const formFeedback = document.getElementById("formFeedback");
  const refreshDashboardBtn = document.getElementById("refreshDashboardBtn");
  const demoDataBtn = document.getElementById("demoDataBtn");
  const downloadPdfBtn = document.getElementById("downloadPdfBtn");
  const downloadPdfBannerBtn = document.getElementById("downloadPdfBannerBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const searchTableInput = document.getElementById("searchTableInput");
  const exportCsvBtn = document.getElementById("exportCsvBtn");
  const simSlider = document.getElementById("simSlider");
  const simUnitsLabel = document.getElementById("simUnitsLabel");
  const simTotalBill = document.getElementById("simTotalBill");
  const simEffectiveRate = document.getElementById("simEffectiveRate");
  const simSlabTier = document.getElementById("simSlabTier");
  const toastNotification = document.getElementById("toastNotification");

  // Tariff Modal Elements
  const tariffModal = document.getElementById("tariffModal");
  const toggleTariffModalBtn = document.getElementById("toggleTariffModalBtn");
  const closeTariffModalBtn = document.getElementById("closeTariffModalBtn");
  const cancelTariffBtn = document.getElementById("cancelTariffBtn");
  const saveTariffBtn = document.getElementById("saveTariffBtn");
  const tariffPresetSelect = document.getElementById("tariffPresetSelect");
  const tariffFixedCharge = document.getElementById("tariffFixedCharge");
  const tariffTaxRate = document.getElementById("tariffTaxRate");
  const tariffSlabPreview = document.getElementById("tariffSlabPreview");

  // ==========================================================
  // TOAST NOTIFICATIONS
  // ==========================================================
  function showToast(message, isError = false) {
    if (!toastNotification) return;
    toastNotification.textContent = message;
    toastNotification.style.borderColor = isError ? "var(--rose)" : "var(--primary)";
    toastNotification.style.display = "block";
    setTimeout(() => {
      toastNotification.style.display = "none";
    }, 3800);
  }

  // ==========================================================
  // 1. REAL-TIME METER READING CALCULATION (MODULE 3)
  // ==========================================================
  function updateLiveConsumption() {
    const prev = parseFloat(prevReadingInput.value);
    const curr = parseFloat(currReadingInput.value);

    if (isNaN(prev) || isNaN(curr)) {
      previewKwh.textContent = "0.00";
      previewCost.textContent = "0.00";
      mathEquation.textContent = "Enter previous and current readings above to calculate kWh consumed.";
      formFeedback.textContent = "";
      return;
    }

    if (curr < prev) {
      previewKwh.textContent = "0.00";
      previewCost.textContent = "0.00";
      mathEquation.textContent = `Warning: Current reading (${curr}) cannot be less than previous reading (${prev}).`;
      formFeedback.className = "form-feedback error";
      formFeedback.textContent = "Current reading must be ≥ previous reading.";
      return;
    }

    const units = Math.max(0, curr - prev);
    previewKwh.textContent = units.toFixed(2);
    mathEquation.textContent = `Current Reading (${curr.toFixed(2)}) − Previous Reading (${prev.toFixed(2)}) = ${units.toFixed(2)} kWh`;

    // Dynamic cost preview (TNEB base rate tier)
    const estCost = (units * 2.25).toFixed(2);
    previewCost.textContent = estCost;
    formFeedback.textContent = "";
  }

  prevReadingInput.addEventListener("input", updateLiveConsumption);
  currReadingInput.addEventListener("input", updateLiveConsumption);

  // ==========================================================
  // 2. FETCH & POPULATE DASHBOARD DATA (MODULE 1, 4, 5, 6, 7, 8)
  // ==========================================================
  async function loadDashboard() {
    try {
      const response = await fetch("/api/dashboard");
      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to load dashboard data.");
      }

      const data = await response.json();
      currentDashboardData = data;

      // Update User profile
      if (data.user) {
        document.getElementById("userName").textContent = data.user.name;
        document.getElementById("userEmail").textContent = data.user.email;
        document.getElementById("userAvatar").textContent = data.user.name.charAt(0).toUpperCase();
      }

      // Update Dates
      if (data.today_date) {
        readingDateInput.value = data.today_date;
        const dObj = new Date(data.today_date + "T12:00:00");
        document.getElementById("currentDateStr").textContent = dObj.toLocaleDateString("en-IN", {
          weekday: "short",
          day: "2-digit",
          month: "short",
          year: "numeric"
        });
      }

      // Pre-fill previous reading suggested
      if (data.suggested_prev_reading !== undefined) {
        prevReadingInput.value = data.suggested_prev_reading.toFixed(2);
      }

      // Update KPI Cards
      const analytics = data.analytics || {};
      document.getElementById("kpiTodayKwh").textContent = (analytics.today_kwh || 0).toFixed(2);
      document.getElementById("kpiTodayCost").textContent = "₹" + (analytics.today_cost || 0).toFixed(2);
      document.getElementById("kpiMonthKwh").textContent = (analytics.current_month_kwh || 0).toFixed(2);
      document.getElementById("kpiMonthBill").textContent = (analytics.current_month_bill || 0).toFixed(2);
      const dailyAvgEl = document.getElementById("kpiDailyAvg");
      if (dailyAvgEl) dailyAvgEl.textContent = (analytics.daily_average_kwh || 0).toFixed(2);

      const peakDayEl = document.getElementById("kpiPeakDay");
      if (peakDayEl) {
        if (analytics.peak_day && analytics.peak_day.kwh) {
          peakDayEl.textContent = `${analytics.peak_day.kwh} kWh (${analytics.peak_day.date})`;
        } else {
          peakDayEl.textContent = "—";
        }
      }

      // Tariff preset indicator
      if (data.tariff && data.tariff.preset_name) {
        document.getElementById("kpiTariffPreset").textContent = data.tariff.preset_name.replace("_", " ");
      }

      // Module 6 & 7: ML Forecast KPI
      const ml = data.forecasting || {};
      document.getElementById("kpiForecastKwh").textContent = (ml.month_forecast_kwh || 0).toFixed(2);
      document.getElementById("kpiForecastBill").textContent = "₹" + (ml.predicted_bill || 0).toFixed(2);

      // Render Progressive Tariff Slab Card (Module 4)
      renderSlabBreakdown(analytics.current_bill_breakdown);

      // Render ML Forecasting Card & Chart (Module 6 & 7)
      renderMLCard(ml);

      // Fetch all readings for charts & history
      await loadReadingsTable();

      // Render Monthly Comparison Chart (Module 5)
      renderMonthCompareChart(analytics.monthly_comparison);

      // Update Simulator with current month usage
      if (analytics.current_month_kwh > 0) {
        simSlider.value = Math.round(analytics.current_month_kwh);
        triggerSimulation(Math.round(analytics.current_month_kwh));
      } else {
        triggerSimulation(265);
      }

    } catch (err) {
      console.error("Dashboard error:", err);
      showToast("Error loading dashboard data: " + err.message, true);
    }
  }

  // ==========================================================
  // 3. RENDER PROGRESSIVE TARIFF SLABS (MODULE 4)
  // ==========================================================
  function renderSlabBreakdown(billData) {
    const listContainer = document.getElementById("slabProgressList");
    if (!billData || !listContainer) return;

    listContainer.innerHTML = "";

    const breakdown = billData.breakdown || [];
    breakdown.forEach((slab) => {
      const row = document.createElement("div");
      row.className = "slab-row-item";

      const units = slab.units || 0;
      const rateStr = slab.rate === 0 ? "FREE (Subsidized)" : `₹${slab.rate.toFixed(2)}/unit`;
      const costStr = slab.cost === 0 ? "₹0.00" : `₹${slab.cost.toFixed(2)}`;

      // Approximate capacity for visual bar
      const maxCap = slab.rate === 0 ? 100 : 200;
      const pct = Math.min(100, (units / maxCap) * 100);

      row.innerHTML = `
        <div class="slab-meta">
          <span class="slab-tier-label">${slab.label} <small style="color: var(--text-dim);">(${rateStr})</small></span>
          <span class="slab-tier-cost">${units.toFixed(2)} units &bull; <b>${costStr}</b></span>
        </div>
        <div class="slab-bar-track">
          <div class="slab-bar-fill ${pct >= 100 ? 'full' : ''}" style="width: ${pct}%;"></div>
        </div>
      `;
      listContainer.appendChild(row);
    });

    document.getElementById("billEnergyCharges").textContent = `₹${(billData.energy_charges || 0).toFixed(2)}`;
    document.getElementById("billFixedCharge").textContent = `₹${(billData.fixed_charge || 50).toFixed(2)}`;
    document.getElementById("billTax").textContent = `₹${(billData.tax_amount || 0).toFixed(2)}`;
    document.getElementById("billTotalAmount").textContent = `₹${(billData.total_bill || 0).toFixed(2)}`;
  }

  // ==========================================================
  // 4. RENDER SCIKIT-LEARN ML FORECAST (MODULE 6 & 7)
  // ==========================================================
  function renderMLCard(ml) {
    if (!ml) return;

    document.getElementById("mlR2Score").textContent = (ml.r2_score || 0).toFixed(4);
    document.getElementById("mlEquation").textContent = ml.formula || "y = mx + c";
    document.getElementById("mlTrendDesc").textContent = ml.trend || "Analyzing trend...";
    document.getElementById("mlForecastUnits").textContent = `${(ml.month_forecast_kwh || 0).toFixed(2)} kWh`;
    document.getElementById("mlForecastCost").textContent = `₹${(ml.predicted_bill || 0).toFixed(2)}`;

    // Render Scikit-learn Forecast Chart
    const ctx = document.getElementById("forecastChart");
    if (!ctx) return;

    if (forecastChartInstance) {
      forecastChartInstance.destroy();
    }

    const histDates = (ml.history_dates || []).map(d => {
      const p = d.split("-");
      return `${p[1]}/${p[2]}`;
    });
    const histVals = ml.history_values || [];
    const regLine = ml.regression_line || [];

    // Future points
    const projDates = ml.projected_dates || [];
    const projVals = ml.projected_values || [];

    // Combine labels: history + future
    const combinedLabels = [...histDates, ...projDates];

    // Historical dataset: filled for hist, null for future
    const actualData = [...histVals, ...new Array(projDates.length).fill(null)];

    // Regression line on historical data
    const fitData = [...regLine, ...new Array(projDates.length).fill(null)];

    // Projected future line: starts at last actual and continues
    const lastHistVal = histVals.length > 0 ? histVals[histVals.length - 1] : null;
    const futureData = new Array(histVals.length - 1).fill(null);
    if (lastHistVal !== null) {
      futureData.push(lastHistVal);
    }
    futureData.push(...projVals);

    forecastChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: combinedLabels,
        datasets: [
          {
            label: "Actual Daily Usage (kWh)",
            data: actualData,
            borderColor: "#23483B",
            backgroundColor: "rgba(35, 72, 59, 0.12)",
            borderWidth: 2.5,
            pointRadius: 3,
            fill: true,
            tension: 0.25
          },
          {
            label: "Linear Regression Fit",
            data: fitData,
            borderColor: "#C39A45",
            borderWidth: 2,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false
          },
          {
            label: "ML 30-Day Projection",
            data: futureData,
            borderColor: "#4E8D38",
            backgroundColor: "rgba(212, 237, 121, 0.25)",
            borderWidth: 2.5,
            borderDash: [6, 4],
            pointRadius: 3,
            fill: true,
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#23483B",
            borderColor: "#D4ED79",
            borderWidth: 1,
            titleColor: "#FFFFFF",
            bodyColor: "#D4ED79",
            callbacks: {
              label: function (ctx) {
                if (ctx.parsed.y !== null) {
                  return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} kWh`;
                }
                return "";
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(35, 72, 59, 0.08)" },
            ticks: { color: "#526359", font: { size: 11, weight: "600" } }
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(35, 72, 59, 0.08)" },
            ticks: { color: "#526359", font: { size: 11, weight: "600" } },
            title: { display: true, text: "Energy (kWh)", color: "#23483B", font: { size: 12, weight: "700" } }
          }
        }
      }
    });
  }

  // ==========================================================
  // 5. RENDER DAILY TREND CHART (MODULE 5)
  // ==========================================================
  function renderDailyTrendChart(readings) {
    const ctx = document.getElementById("dailyTrendChart");
    if (!ctx) return;

    if (dailyTrendChartInstance) {
      dailyTrendChartInstance.destroy();
    }

    const sorted = [...readings].sort((a, b) => a.reading_date.localeCompare(b.reading_date));
    const labels = sorted.map(r => {
      const p = r.reading_date.split("-");
      return `${p[1]}/${p[2]}`;
    });
    const values = sorted.map(r => r.kwh);

    dailyTrendChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Daily Consumption (kWh)",
          data: values,
          borderColor: "#23483B",
          backgroundColor: "rgba(212, 237, 121, 0.2)",
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointRadius: 3.5,
          pointBackgroundColor: "#D4ED79",
          pointBorderColor: "#23483B"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#23483B",
            borderColor: "#D4ED79",
            borderWidth: 1,
            titleColor: "#FFFFFF",
            bodyColor: "#D4ED79"
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(35, 72, 59, 0.08)" },
            ticks: { color: "#526359", font: { size: 11, weight: "600" } }
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(35, 72, 59, 0.08)" },
            ticks: { color: "#526359", font: { size: 11, weight: "600" } },
            title: { display: true, text: "kWh Consumed", color: "#23483B", font: { size: 12, weight: "700" } }
          }
        }
      }
    });
  }

  // ==========================================================
  // 6. RENDER MONTH-TO-MONTH COMPARISON (MODULE 5 - SLIDE 10)
  // ==========================================================
  function renderMonthCompareChart(monthlyComparison) {
    const ctx = document.getElementById("monthCompareChart");
    const insightBox = document.getElementById("compareInsightText");
    if (!ctx || !monthlyComparison) return;

    if (monthCompareChartInstance) {
      monthCompareChartInstance.destroy();
    }

    const labels = monthlyComparison.map(m => m.month_name);
    const kwhData = monthlyComparison.map(m => m.total_kwh);
    const billData = monthlyComparison.map(m => m.bill);

    monthCompareChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Total Consumption (kWh)",
            data: kwhData,
            backgroundColor: "#23483B",
            borderColor: "#18372D",
            borderWidth: 1,
            borderRadius: 6,
            yAxisID: "y"
          },
          {
            label: "Estimated Bill (₹)",
            data: billData,
            backgroundColor: "#D4ED79",
            borderColor: "#B9D95B",
            borderWidth: 1,
            borderRadius: 6,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: { color: "#23483B", font: { size: 11, weight: "700" } }
          },
          tooltip: {
            backgroundColor: "#23483B",
            borderColor: "#D4ED79",
            borderWidth: 1,
            titleColor: "#FFFFFF",
            bodyColor: "#D4ED79"
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#526359", font: { weight: "600" } }
          },
          y: {
            type: "linear",
            display: true,
            position: "left",
            beginAtZero: true,
            grid: { color: "rgba(35, 72, 59, 0.08)" },
            ticks: { color: "#23483B", font: { weight: "600" } },
            title: { display: true, text: "Consumption (kWh)", color: "#23483B", font: { weight: "700" } }
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            beginAtZero: true,
            grid: { drawOnChartArea: false },
            ticks: { color: "#426B52", font: { weight: "600" } },
            title: { display: true, text: "Estimated Bill (₹)", color: "#426B52", font: { weight: "700" } }
          }
        }
      }
    });

    // Provide Slide 10 style insight text
    if (monthlyComparison.length >= 2) {
      const lastM = monthlyComparison[monthlyComparison.length - 1];
      const prevM = monthlyComparison[monthlyComparison.length - 2];
      const diff = (lastM.total_kwh - prevM.total_kwh).toFixed(2);
      const sign = diff >= 0 ? "+" : "";
      insightBox.innerHTML = `
        <b>📊 Month-to-Month Variance Analysis:</b><br/>
        Comparing <b>${prevM.month_name} (${prevM.total_kwh} kWh)</b> against <b>${lastM.month_name} (${lastM.total_kwh} kWh)</b>: 
        Consumption changed by <span style="color: ${diff >= 0 ? '#fca5a5' : '#6ee7b7'}; font-weight: 700;">${sign}${diff} kWh (${sign}${lastM.pct_change}%)</span>.
        Estimated billing changed from <b>₹${prevM.bill}</b> to <b>₹${lastM.bill}</b>.
      `;
    } else if (monthlyComparison.length === 1) {
      insightBox.innerHTML = `<b>📊 Single Month Record:</b> <b>${monthlyComparison[0].month_name}</b> logged <b>${monthlyComparison[0].total_kwh} kWh</b> totaling <b>₹${monthlyComparison[0].bill}</b>.`;
    } else {
      insightBox.textContent = "Log daily meter readings across 2 or more months to unlock automatic comparative analytics.";
    }
  }

  // ==========================================================
  // 7. LOAD & FILTER READINGS TABLE (MODULE 2)
  // ==========================================================
  async function loadReadingsTable() {
    const tableBody = document.getElementById("readingsTableBody");
    if (!tableBody) return;

    try {
      const res = await fetch("/api/readings?days=365");
      const data = await res.json();
      allReadingsList = data.readings || [];

      renderTableRows(allReadingsList);
      renderDailyTrendChart(allReadingsList);

    } catch (err) {
      console.error(err);
      tableBody.innerHTML = `<tr><td colspan="7" class="empty-state">Failed to load meter history.</td></tr>`;
    }
  }

  function renderTableRows(readings) {
    const tableBody = document.getElementById("readingsTableBody");
    if (!tableBody) return;

    if (!readings || readings.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="empty-state">No meter readings logged yet. Use the form above to add your first reading or click 'Load PPT Demo Data'.</td></tr>`;
      return;
    }

    tableBody.innerHTML = "";
    readings.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b>${r.reading_date}</b></td>
        <td><span class="badge-tag">${r.appliance || 'Main Household Meter'}</span></td>
        <td>${r.previous_reading !== null ? Number(r.previous_reading).toFixed(2) : '—'}</td>
        <td>${r.current_reading !== null ? Number(r.current_reading).toFixed(2) : '—'}</td>
        <td><b style="color: #23483B; font-weight: 700;">${Number(r.kwh).toFixed(2)} kWh</b></td>
        <td><b style="color: #2E7D32; font-weight: 700;">₹${Number(r.cost).toFixed(2)}</b></td>
        <td>
          <button type="button" class="del-btn" data-id="${r.id}">Delete</button>
        </td>
      `;
      tableBody.appendChild(tr);
    });

    // Attach delete listeners
    document.querySelectorAll(".del-btn").forEach((btn) => {
      btn.addEventListener("click", async function () {
        const id = this.getAttribute("data-id");
        if (!confirm("Are you sure you want to delete this meter reading?")) return;

        try {
          const delRes = await fetch(`/api/readings/${id}`, { method: "DELETE" });
          if (delRes.ok) {
            showToast("Reading deleted successfully.");
            await loadDashboard();
          } else {
            showToast("Could not delete reading.", true);
          }
        } catch (err) {
          showToast("Network error deleting reading.", true);
        }
      });
    });
  }

  // Search filter
  if (searchTableInput) {
    searchTableInput.addEventListener("input", function () {
      const q = this.value.toLowerCase().trim();
      if (!q) {
        renderTableRows(allReadingsList);
        return;
      }
      const filtered = allReadingsList.filter(r => 
        (r.reading_date && r.reading_date.toLowerCase().includes(q)) ||
        (r.appliance && r.appliance.toLowerCase().includes(q))
      );
      renderTableRows(filtered);
    });
  }

  // Export CSV
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener("click", function () {
      if (!allReadingsList.length) {
        showToast("No data to export.", true);
        return;
      }
      let csv = "Date,Appliance,Previous_Reading,Current_Reading,Units_Consumed_kWh,Cost_INR\n";
      allReadingsList.forEach(r => {
        csv += `"${r.reading_date}","${r.appliance || 'Main Meter'}",${r.previous_reading || 0},${r.current_reading || 0},${r.kwh || 0},${r.cost || 0}\n`;
      });
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.setAttribute("download", `Meter_Readings_Export_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  }

  // ==========================================================
  // 8. FORM SUBMISSION (MODULE 2 & 3)
  // ==========================================================
  meterForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    formFeedback.textContent = "";

    const dateVal = readingDateInput.value;
    const applianceVal = meterApplianceInput.value;
    const prevVal = parseFloat(prevReadingInput.value);
    const currVal = parseFloat(currReadingInput.value);

    if (!dateVal || isNaN(prevVal) || isNaN(currVal)) {
      formFeedback.className = "form-feedback error";
      formFeedback.textContent = "Please fill in all meter reading fields.";
      return;
    }

    if (currVal < prevVal) {
      formFeedback.className = "form-feedback error";
      formFeedback.textContent = "Current reading must be ≥ previous reading.";
      return;
    }

    const saveBtn = document.getElementById("saveReadingBtn");
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving reading...";

    try {
      const res = await fetch("/api/readings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reading_date: dateVal,
          appliance: applianceVal,
          previous_reading: prevVal,
          current_reading: currVal
        })
      });
      const data = await res.json();

      if (!res.ok) {
        formFeedback.className = "form-feedback error";
        formFeedback.textContent = data.error || "Failed to save reading.";
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<span>➕</span> Save Daily Meter Reading`;
        return;
      }

      showToast(`Reading saved! Consumed: ${data.reading.kwh} kWh`);
      formFeedback.className = "form-feedback success";
      formFeedback.textContent = `Saved ${data.reading.kwh} kWh successfully!`;

      // Update suggested previous reading for next entry
      prevReadingInput.value = currVal.toFixed(2);
      currReadingInput.value = "";
      previewKwh.textContent = "0.00";
      previewCost.textContent = "0.00";

      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span>➕</span> Save Daily Meter Reading`;

      // Refresh entire dashboard with updated calculations
      await loadDashboard();

    } catch (err) {
      console.error(err);
      formFeedback.className = "form-feedback error";
      formFeedback.textContent = "Network error. Please make sure Flask is running.";
      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span>➕</span> Save Daily Meter Reading`;
    }
  });

  // Reset form
  document.getElementById("resetFormBtn").addEventListener("click", function () {
    currReadingInput.value = "";
    previewKwh.textContent = "0.00";
    previewCost.textContent = "0.00";
    formFeedback.textContent = "";
    updateLiveConsumption();
  });

  // ==========================================================
  // 9. ONE-CLICK REALISTIC PPT DEMO DATA LOADER (SLIDE 10)
  // ==========================================================
  if (demoDataBtn) {
    demoDataBtn.addEventListener("click", async function () {
      if (!confirm("This will load 60 days of realistic meter readings matching PPT Slide 10 (Month 1: 230 kWh, Month 2: 265 kWh, Today: 9 kWh, Forecast: 278 kWh). Continue?")) {
        return;
      }

      demoDataBtn.disabled = true;
      demoDataBtn.textContent = "Loading 60D dataset...";

      try {
        const res = await fetch("/api/demo-data", { method: "POST" });
        const data = await res.json();

        if (res.ok) {
          showToast(data.message || "PPT Demo Dataset Loaded!");
          await loadDashboard();
        } else {
          showToast(data.error || "Failed to load demo data.", true);
        }
      } catch (err) {
        showToast("Error loading demo dataset.", true);
      } finally {
        demoDataBtn.disabled = false;
        demoDataBtn.innerHTML = `<span>⚡</span> Load PPT Demo Data (60D)`;
      }
    });
  }

  // ==========================================================
  // 10. INTERACTIVE "WHAT-IF" SIMULATOR
  // ==========================================================
  function triggerSimulation(units) {
    simUnitsLabel.textContent = units;
    
    // TNEB Domestic Progressive Slab calculation
    let remaining = units;
    let cost = 0;
    let slabTierName = "Slab 1 (0 - 100 Free)";

    if (remaining <= 100) {
      cost = 0;
      slabTierName = "Slab 1 (0 - 100 Free Subsidized)";
    } else {
      // 0-100: 0
      remaining -= 100;

      // 101-200: 2.25
      const slab2 = Math.min(remaining, 100);
      cost += slab2 * 2.25;
      remaining -= slab2;
      slabTierName = "Slab 2 (101 - 200 units)";

      if (remaining > 0) {
        // 201-400: 4.50
        const slab3 = Math.min(remaining, 200);
        cost += slab3 * 4.50;
        remaining -= slab3;
        slabTierName = "Slab 3 (201 - 400 units)";

        if (remaining > 0) {
          // 401-500: 6.00
          const slab4 = Math.min(remaining, 100);
          cost += slab4 * 6.00;
          remaining -= slab4;
          slabTierName = "Slab 4 (401 - 500 units)";

          if (remaining > 0) {
            // > 500: 8.00
            cost += remaining * 8.00;
            slabTierName = "Slab 5 (> 500 units High Demand)";
          }
        }
      }
    }

    const fixedCharge = 50.0;
    const tax = (cost + fixedCharge) * 0.05;
    const total = cost + fixedCharge + tax;
    const effectiveRate = units > 0 ? (total / units).toFixed(2) : "0.00";

    simTotalBill.textContent = `₹${total.toFixed(2)}`;
    simEffectiveRate.textContent = `₹${effectiveRate} / kWh`;
    simSlabTier.textContent = slabTierName;
  }

  simSlider.addEventListener("input", function () {
    triggerSimulation(parseInt(this.value, 10));
  });

  // ==========================================================
  // 11. PDF REPORT GENERATION (REPORTLAB BACKEND)
  // ==========================================================
  function triggerPdfDownload() {
    showToast("Generating official PDF energy audit report...");
    window.location.href = "/api/report";
  }

  if (downloadPdfBtn) downloadPdfBtn.addEventListener("click", triggerPdfDownload);
  if (downloadPdfBannerBtn) downloadPdfBannerBtn.addEventListener("click", triggerPdfDownload);

  // ==========================================================
  // 12. TARIFF SETTINGS MODAL
  // ==========================================================
  toggleTariffModalBtn.addEventListener("click", () => {
    tariffModal.style.display = "flex";
    renderTariffModalPreview();
  });

  function closeTariffModal() {
    tariffModal.style.display = "none";
  }

  closeTariffModalBtn.addEventListener("click", closeTariffModal);
  cancelTariffBtn.addEventListener("click", closeTariffModal);

  tariffPresetSelect.addEventListener("change", renderTariffModalPreview);

  function renderTariffModalPreview() {
    const preset = tariffPresetSelect.value;
    if (preset === "TNEB_Domestic") {
      tariffFixedCharge.value = 50;
      tariffTaxRate.value = 5;
      tariffSlabPreview.innerHTML = `
        <div style="font-size: 0.78rem; line-height: 1.6; color: #cbd5e1;">
          &bull; <b>0 - 100 units:</b> ₹0.00 / unit (Free 100 Units Subsidy)<br/>
          &bull; <b>101 - 200 units:</b> ₹2.25 / unit<br/>
          &bull; <b>201 - 400 units:</b> ₹4.50 / unit<br/>
          &bull; <b>401 - 500 units:</b> ₹6.00 / unit<br/>
          &bull; <b>Above 500 units:</b> ₹8.00 / unit
        </div>
      `;
    } else if (preset === "Standard_Tiered") {
      tariffFixedCharge.value = 80;
      tariffTaxRate.value = 5;
      tariffSlabPreview.innerHTML = `
        <div style="font-size: 0.78rem; line-height: 1.6; color: #cbd5e1;">
          &bull; <b>0 - 100 units:</b> ₹3.50 / unit<br/>
          &bull; <b>101 - 300 units:</b> ₹5.00 / unit<br/>
          &bull; <b>301 - 500 units:</b> ₹7.00 / unit<br/>
          &bull; <b>Above 500 units:</b> ₹9.50 / unit
        </div>
      `;
    } else {
      tariffFixedCharge.value = 150;
      tariffTaxRate.value = 9;
      tariffSlabPreview.innerHTML = `
        <div style="font-size: 0.78rem; line-height: 1.6; color: #cbd5e1;">
          &bull; <b>0 - 200 units:</b> ₹7.50 / unit<br/>
          &bull; <b>201 - 500 units:</b> ₹9.00 / unit<br/>
          &bull; <b>Above 500 units:</b> ₹11.50 / unit
        </div>
      `;
    }
  }

  saveTariffBtn.addEventListener("click", async function () {
    const preset = tariffPresetSelect.value;
    const fixed = parseFloat(tariffFixedCharge.value) || 50;
    const tax = parseFloat(tariffTaxRate.value) || 5;

    let slabs = [];
    if (preset === "TNEB_Domestic") {
      slabs = [
        { limit: 100, rate: 0.0, label: "0 - 100 units (Subsidized)" },
        { limit: 200, rate: 2.25, label: "101 - 200 units" },
        { limit: 400, rate: 4.50, label: "201 - 400 units" },
        { limit: 500, rate: 6.00, label: "401 - 500 units" },
        { limit: null, rate: 8.00, label: "Above 500 units" }
      ];
    } else if (preset === "Standard_Tiered") {
      slabs = [
        { limit: 100, rate: 3.50, label: "0 - 100 units" },
        { limit: 300, rate: 5.00, label: "101 - 300 units" },
        { limit: 500, rate: 7.00, label: "301 - 500 units" },
        { limit: null, rate: 9.50, label: "Above 500 units" }
      ];
    } else {
      slabs = [
        { limit: 200, rate: 7.50, label: "0 - 200 units" },
        { limit: 500, rate: 9.00, label: "201 - 500 units" },
        { limit: null, rate: 11.50, label: "Above 500 units" }
      ];
    }

    try {
      const res = await fetch("/api/tariff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset_name: preset,
          slabs: slabs,
          fixed_charge: fixed,
          tax_rate: tax
        })
      });
      if (res.ok) {
        showToast("Tariff settings updated!");
        closeTariffModal();
        await loadDashboard();
      }
    } catch (err) {
      showToast("Error updating tariff.", true);
    }
  });

  // ==========================================================
  // 13. REFRESH & LOGOUT
  // ==========================================================
  refreshDashboardBtn.addEventListener("click", async function () {
    refreshDashboardBtn.classList.add("rotating");
    await loadDashboard();
    setTimeout(() => refreshDashboardBtn.classList.remove("rotating"), 500);
    showToast("Dashboard refreshed!");
  });

  logoutBtn.addEventListener("click", async function () {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    } catch (err) {
      window.location.href = "/login";
    }
  });

  // ==========================================================
  // 14. INITIALIZE DASHBOARD
  // ==========================================================
  loadDashboard();
});