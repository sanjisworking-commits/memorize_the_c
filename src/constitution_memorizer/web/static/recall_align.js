/* Shared recall alignment (LCS) for Type / Recite accuracy maps.
 * Keep logic in sync with constitution_memorizer.web.recall_align.
 */
(function (global) {
  function normWord(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  function tokenize(text) {
    const stripped = String(text || "").trim();
    if (!stripped) {
      return [];
    }
    return stripped.split(/\s+/);
  }

  function alignTokens(sourceWords, spokenWords) {
    const src = sourceWords.slice();
    const spk = spokenWords.slice();
    const srcNorm = src.map(normWord);
    const spkNorm = spk.map(normWord);
    const n = srcNorm.length;
    const m = spkNorm.length;

    const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));
    for (let i = 1; i <= n; i += 1) {
      for (let j = 1; j <= m; j += 1) {
        if (srcNorm[i - 1] && srcNorm[i - 1] === spkNorm[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    const hitIndices = new Set();
    const spokenHitIndices = new Set();
    let i = n;
    let j = m;
    while (i > 0 && j > 0) {
      if (srcNorm[i - 1] && srcNorm[i - 1] === spkNorm[j - 1]) {
        hitIndices.add(i - 1);
        spokenHitIndices.add(j - 1);
        i -= 1;
        j -= 1;
      } else if (dp[i - 1][j] >= dp[i][j - 1]) {
        i -= 1;
      } else {
        j -= 1;
      }
    }

    const extras = [];
    for (let k = 0; k < m; k += 1) {
      if (!spokenHitIndices.has(k) && spkNorm[k]) {
        extras.push(spk[k]);
      }
    }

    const hits = hitIndices.size;
    const total = src.length;
    const percent = total ? Math.round((100 * hits) / total) : 0;

    return {
      sourceWords: src,
      spokenWords: spk,
      hitIndices,
      spokenHitIndices,
      extras,
      hits,
      total,
      percent,
      statsLabel: hits + " / " + total + " recalled · " + percent + "%",
    };
  }

  function alignText(sourceText, spokenText) {
    return alignTokens(tokenize(sourceText), tokenize(spokenText));
  }

  global.RecallAlign = {
    normWord,
    tokenize,
    alignTokens,
    alignText,
  };
})(typeof window !== "undefined" ? window : globalThis);
