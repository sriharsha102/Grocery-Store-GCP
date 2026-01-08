// ====== CONFIG ======
const SHEET_ID = '17GkeFx96KS1udbTqu-MnCliq-v3FzDPHWUg4C84EL8M';
const FROM_NAME = 'Bharat Bazar';
const REPLY_TO = 'developers@lightningminds.com';

// Optional: Filter specific tabs (leave empty to include all)
const TAB_ALLOWLIST = []; // e.g., ['Inventory', 'Veggies'] - empty means all tabs
const TAB_DENYLIST = []; // e.g., ['Template', 'Archive'] - tabs to exclude

// ====== HELPERS ======
function currency_(n) {
  return '$' + Number(n).toFixed(2);
}

/**
 * Get price map from ALL tabs (or filtered tabs)
 * Returns: { item_name_lowercase: price }
 */
function getPriceMap_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const allSheets = ss.getSheets();
  const priceMap = {};

  // Filter tabs if allowlist/denylist configured
  const allowlistLower = TAB_ALLOWLIST.map(t => t.toLowerCase());
  const denylistLower = TAB_DENYLIST.map(t => t.toLowerCase());

  for (const sheet of allSheets) {
    const tabName = sheet.getName();
    const tabNameLower = tabName.toLowerCase();

    // Apply filters
    if (TAB_ALLOWLIST.length > 0 && !allowlistLower.includes(tabNameLower)) {
      Logger.log(`Skipping tab '${tabName}' (not in allowlist)`);
      continue;
    }
    if (TAB_DENYLIST.length > 0 && denylistLower.includes(tabNameLower)) {
      Logger.log(`Skipping tab '${tabName}' (in denylist)`);
      continue;
    }

    try {
      const lastRow = sheet.getLastRow();
      if (lastRow < 2) {
        Logger.log(`Tab '${tabName}' has no data rows, skipping`);
        continue;
      }

      // Read header row to find name and price columns
      const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
      const nameColIdx = headers.findIndex(h => String(h).toLowerCase() === 'name');
      const priceColIdx = headers.findIndex(h => String(h).toLowerCase() === 'price');

      if (nameColIdx === -1 || priceColIdx === -1) {
        Logger.log(`Tab '${tabName}' missing 'name' or 'price' column, skipping`);
        continue;
      }

      // Read data rows (A2:Z or as many columns as needed)
      const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

      for (const row of values) {
        const name = row[nameColIdx];
        const price = row[priceColIdx];

        if (!name) continue;

        const itemKey = String(name).trim().toLowerCase();
        const itemPrice = Number(price) || 0;

        // If item exists in multiple tabs, last tab wins
        // (You could add warning logic here if needed)
        priceMap[itemKey] = itemPrice;
      }

      Logger.log(`Tab '${tabName}': Added ${Object.keys(priceMap).length} items to price map`);
    } catch (err) {
      Logger.log(`Error processing tab '${tabName}': ${err}`);
      continue;
    }
  }

  Logger.log(`Total items in price map: ${Object.keys(priceMap).length}`);
  return priceMap;
}

/**
 * Get weight map from ALL tabs (or filtered tabs)
 * Returns: { item_name_lowercase: weight }
 */
function getWeightMap_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const allSheets = ss.getSheets();
  const weightMap = {};

  // Filter tabs if allowlist/denylist configured
  const allowlistLower = TAB_ALLOWLIST.map(t => t.toLowerCase());
  const denylistLower = TAB_DENYLIST.map(t => t.toLowerCase());

  for (const sheet of allSheets) {
    const tabName = sheet.getName();
    const tabNameLower = tabName.toLowerCase();

    // Apply filters
    if (TAB_ALLOWLIST.length > 0 && !allowlistLower.includes(tabNameLower)) {
      Logger.log(`Skipping tab '${tabName}' (not in allowlist)`);
      continue;
    }
    if (TAB_DENYLIST.length > 0 && denylistLower.includes(tabNameLower)) {
      Logger.log(`Skipping tab '${tabName}' (in denylist)`);
      continue;
    }

    try {
      const lastRow = sheet.getLastRow();
      if (lastRow < 2) {
        Logger.log(`Tab '${tabName}' has no data rows, skipping`);
        continue;
      }

      // Read header row to find name and weight columns
      const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
      const nameColIdx = headers.findIndex(h => String(h).toLowerCase() === 'name');
      const weightColIdx = headers.findIndex(h => String(h).toLowerCase() === 'weight');

      if (nameColIdx === -1 || weightColIdx === -1) {
        Logger.log(`Tab '${tabName}' missing 'name' or 'weight' column, skipping`);
        continue;
      }

      // Read data rows (A2:Z or as many columns as needed)
      const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

      for (const row of values) {
        const name = row[nameColIdx];
        const weight = row[weightColIdx];

        if (!name) continue;

        const itemKey = String(name).trim().toLowerCase();
        const itemWeight = String(weight || '').trim();

        if (itemWeight) {
          weightMap[itemKey] = itemWeight;
        }
      }

      Logger.log(`Tab '${tabName}': Added ${Object.keys(weightMap).length} items to weight map`);
    } catch (err) {
      Logger.log(`Error processing tab '${tabName}': ${err}`);
      continue;
    }
  }

  Logger.log(`Total items in weight map: ${Object.keys(weightMap).length}`);
  return weightMap;
}

function buildLineItems_(items, priceMap, weightMap) {
  const lineItems = [];
  let total = 0;

  for (const it of (items || [])) {
    const key = String(it.name || '').trim().toLowerCase();
    const unit = Number(priceMap[key] || 0);
    const qty = Number(it.qty || 0);
    const subtotal = unit * qty;
    const weight = String(weightMap[key] || '').trim();
    total += subtotal;

    // Log if price not found (for debugging)
    if (unit === 0) {
      Logger.log(`Warning: No price found for item '${it.name}' (key: '${key}')`);
    }

    lineItems.push({ name: it.name, qty, unitPrice: unit, subtotal, weight });
  }

  return { lineItems, total };
}

function renderReceiptHtml_(payload, lineItems, total) {
  const rows = lineItems.map(li => `
    <tr>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;">${li.name}</td>
      <td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">${li.qty}</td>
      <td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">${li.weight || ''}</td>
      <td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">${currency_(li.unitPrice)}</td>
      <td style="padding:6px 8px;text-align:right;border-bottom:1px solid #eee;">${currency_(li.subtotal)}</td>
    </tr>`).join('');

  return `
  <div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
    <h2 style="margin:0 0 12px">Thanks for your order!</h2>
    <p style="margin:0 0 16px"><strong>Order:</strong> ${payload.order_id || ''}</p>
    <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;min-width:360px">
      <thead>
        <tr>
          <th style="text-align:left;padding:6px 8px;border-bottom:2px solid #333;">Item</th>
          <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Qty</th>
          <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Weight</th>
          <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Rate</th>
          <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Subtotal</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot>
        <tr>
          <td colspan="4" style="text-align:right;padding:10px 8px;"><strong>Total</strong></td>
          <td style="text-align:right;padding:10px 8px;"><strong>${currency_(total)}</strong></td>
        </tr>
      </tfoot>
    </table>
    <p style="color:#666;margin-top:16px">If you have any questions, contact Bharat Bazar.</p>
  </div>`;
}

// ====== ENTRYPOINT ======
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents || '{}');

    // --- Secret check ---
    const secret = PropertiesService.getScriptProperties()
      .getProperty('EMAIL_WEBHOOK_SECRET');
    if (!payload || payload.secret !== secret) {
      return ContentService
        .createTextOutput(JSON.stringify({ ok: false, error: 'unauthorized' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // ---- ROUTING: receipt vs low_stock ----
    if (payload.type === 'receipt') {
      const o = payload.order || {};
      const to = o.customer_email;
      const subject = `Bharat Bazar receipt - ${o.order_id || ''}`;

      // Build line items from ALL tabs
      const priceMap = getPriceMap_();
      const weightMap = getWeightMap_();
      const { lineItems, total } = buildLineItems_(o.items || [], priceMap, weightMap);

      // HTML + text
      const htmlBody = renderReceiptHtml_(o, lineItems, total);
      const textRows = lineItems
        .map(li => `- ${li.name}${li.weight ? ` (${li.weight})` : ''} x ${li.qty} @ ${currency_(li.unitPrice)} = ${currency_(li.subtotal)}`)
        .join('\n');
      const plainText =
        `Thanks for your order!\n\nOrder: ${o.order_id}\n` +
        `${textRows}\n\nTotal: ${currency_(total)}\n`;

      const mailOptions = {
        htmlBody: htmlBody,
        name: FROM_NAME,
        replyTo: REPLY_TO
      };

      if (payload.owner_email) {
        mailOptions.cc = payload.owner_email;
      }

      MailApp.sendEmail(to, subject, plainText, mailOptions);

      return ContentService
        .createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    if (payload.type === 'low_stock' && payload.owner_email) {
      const lines = (payload.items || [])
        .map(i => `${i.name}: qty ${i.new_qty} (≤10)`)
        .join('\n') || 'No low-stock items found';

      const finalText = "Below are the items with stock less than 10:\n\n" + lines;

      MailApp.sendEmail({
        to: payload.owner_email,
        subject: 'Low stock alert',
        body: finalText,
        name: FROM_NAME,
        replyTo: REPLY_TO,
      });

      return ContentService
        .createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: 'unknown type' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    Logger.log('Error in doPost: ' + err);
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
