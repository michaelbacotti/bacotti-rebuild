# Live Crypto Safety Feed

Latest items from daily link-discovery cron (14-day rolling window). The bithues desk reads every item, groups them by theme, and writes the morning brief below.

## 2026-08-16

### Headline: Phishing Moved Offline This Week: Postal Letters Started Arriving in Switzerland
The threat surface expanded beyond email and Discord this week. A physical-letter campaign and an impersonator app both targeted the same Trezor-shipper breach data.

### Today's signal
The week's most under-reported story is the one that has nothing to do with private keys or seed phrases. The Swiss banking standards body BACS responded to reports this week that physical letters demanding a 'Post-Quantum Cryptography Security Update' — with a deadline and the full corporate branding of a major hardware-wallet vendor — arrived at homes in Switzerland. The same data set that powered the Trezor shipper breach last week (13,689 customers) is now powering a physical-mail phishing campaign. The threat actor has your real address, your real purchase history, and your real order number. The letter is indistinguishable from the vendor's actual communications until you read the small print. Separately, an Ethereum seed-phrase scam app was removed from an app store this week after a test drain proved the workflow worked — the app impersonated a legitimate AI-wallet onboarding flow. The combined lesson: the phishing channel expanded this week, and the standard 'verify by clicking through' guidance no longer applies. Email, mail, and app stores are now all part of the same attack surface.

### Why it matters
- Physical mail bypasses every spam filter and most users' threat models. A letter referencing a real wallet order, a real address, and a real purchase history is qualitatively different from an email — most users do not have a mental model for 'this is a phishing letter.'
- App-store impersonation bypasses the 'I downloaded it from the official store' assumption that most users treat as a safety signal. The fact that the app made it through review proves that store-trust is not a defense.
- The Trezor breach data set (last week) is now being actively weaponized. The lag between breach disclosure and phishing-wave launch is days, not months.
- The 'verify by clicking through' guidance no longer applies when the phishing message references a real address and looks like a real letter. The correct verification path is to open the vendor's site yourself and call their published support number.

### What to do today
- **Treat any inbound message — email, mail, chat, or app — that demands urgent seed-phrase or firmware action as hostile by default.** Verify by opening the vendor's official site yourself. If a physical letter arrives, call the vendor's published support number (from their official site) and ask whether they sent it. They did not.
- **Audit your Trezor order history for breach exposure.** If you ordered from Trezor in the last three years, your shipping data is now in active phishing campaigns. Expect a tailored message within two weeks.
- **Remove any app from your phone that asks for a seed phrase or private key.** No legitimate wallet, exchange, or support workflow requires you to enter a seed phrase in an app. Treat any interface that asks for one as hostile.
- **Update your verification playbook for physical mail.** Add 'I will not respond to any physical letter about a wallet' to your threat-model list. The correct response is to call the vendor directly.

### Key developments
- **Physical letters demanding 'Post-Quantum Cryptography Security Updates' arrived at Swiss homes this week** — https://www.zerberos.com/en/crypto-wallet-phishing-by-mail-when-cybercriminals-use-the-postal-service/
  **What happened:** BACS, the Swiss banking standards body, responded to reports of physical letters arriving at homes demanding a 'Post-Quantum Cryptography Security Update' with a deadline. The letters use the corporate branding of a major hardware-wallet vendor and reference real shipping addresses.
  **Why it matters:** Physical mail bypasses every spam filter and most users' threat models. The phishing channel expanded this week in ways that standard operational-security checklists do not cover.
  **Reader implication:** Treat any physical letter about a wallet as hostile by default. Verify by calling the vendor's published support number (from their official site), not by responding to the letter.
  **Tags:** phishing, operational security, supply-chain attack
  **Severity:** High
- **Fieldfisher: How the Coldcard attack actually unfolded, hour by hour** — https://www.fieldfisher.com/en/insights/coinkite-coldcard-hack-what-victims-need-to-know
  **What happened:** Fieldfisher's deep dive on the attack timeline: first sweep began at 01:31 UTC on July 30, ~594 BTC vanished from ~500 wallets in the first 25 minutes, and the campaign continued in waves. The piece walks victims through what they can and cannot recover.
  **Why it matters:** The operational detail of the attack (the speed, the wave structure, the seed-phrase generation flaw) is now the canonical reference for understanding how a generation-step compromise plays out in practice.
  **Reader implication:** Anyone who generated a Coldcard seed during the affected window should assume the worst. Move funds to a new seed on a different device, not a new wallet on the same device.
  **Tags:** firmware risk, seed-phrase exposure, private-key compromise
  **Severity:** Critical
- **The same whale was drained a third time — this time for $25.6M** — https://cryptoadventure.com/crypto-whale-drained-of-25-6m-in-second-major-phishing-attack/
  **What happened:** The same Ethereum whale address that lost $24M in 2023 and $26M earlier this week was drained again — this time through a malicious token approval that emptied WBTC, cbBTC, LDO, USDS, and CRV before the attacker converted to DAI and ETH. Three different mechanisms, one persistent target.
  **Why it matters:** The address is the persistent identifier. The attack mechanism rotates. The cure is to break the on-chain link to the address entirely.
  **Reader implication:** If your wallet address has been hit before, the address is on a target list. A new seed on the same device does not remove you from the list. A new wallet on a different device with no on-chain link does.
  **Tags:** approval abuse, treasury exposure, phishing
  **Severity:** Critical
  **Confirming source:** https://crypto.news/address-poisoning-attacks-drains-100k-dollars-usdt/

### Items (raw, archived for completeness)
- **List of Reported Scam Companies in 2026 - Part 1 - Crypto Legal** — https://www.cryptolegal.uk/list-of-reported-scam-companies-part-1/
  > Database article, not a development. *Below the editorial bar — vendor database reference, not a development. Dropped.*

### Related reading
- **Seed Phrases: What They Are and How People Lose Them** — /guides/seed-phrases-what-they-are-and-how-people-lose-them/
- **Address Poisoning: The Quiet Cousin of Approval Abuse** — /guides/address-poisoning/
- **The Wallet Safety Checklist** — /tools/wallet-safety-checklist/

---

## 2026-08-17

### Headline: The Week Custody Stopped Being a Device Problem
Five days of incidents converged on the same lesson: the seams in your custody chain are not in your hardware — they are in every vendor that touches it.

### This week's signal
The week opened with a single $116M loss tied to a seven-day bug in Coldcard's seed-phrase generation routine, and ended with three more supply-chain attacks on hardware-wallet vendors that had nothing to do with the cryptography at all. The Coldcard story was the headline. The vendor breaches are the longer lesson. Across the five days of coverage, the dominant pattern was not a new attack class — it was the same attackers moving through adjacent layers of the same custody stack: from the device generation step, to the shipping partner that handled the box, to the order-tracking plug-in that processed the warranty card, to the seed-phrase prompt in the chat app that the user thought was their wallet. The cost of trying for the attacker has collapsed; the value of probing the seams has not changed. Every day this week surfaced another seam. The H1 2026 framing — that roughly three-quarters of all losses trace back to private-key or seed-phrase failure — now needs a footnote. It is not just the cryptography being attacked. It is the operations around the cryptography.

### Why it matters
- The Coldcard bug was a generation-step flaw, not a phishing failure. Wallets created on a Coldcard during the affected window in late July should be considered compromised even when the funds have not yet moved — and the bug demonstrates that "cold storage" is only as strong as the device's entropy source.
- The week's supply-chain attacks (Trezor's shipper, SafePal's order-tracking plug-in, Bits of Gold's vendor) hit vendors whose product did not change. The threat model for anyone holding a hardware wallet now includes the shipping company, the warranty database, and any third-party plug-in attached to the wallet interface.
- A single whale lost roughly $25M three times in one week to the same address cluster — proof that persistent target lists survive across both phishing and private-key compromise vectors, and that the cure is to break the on-chain link to the address entirely.
- Phishing is moving offline: physical letters demanding "Post-Quantum Cryptography Security Updates" reached Switzerland-based users this week, and a seed-phrase scam app was removed after impersonating a legitimate AI-wallet workflow. Email and Discord are no longer the only channels.
- Bitcoin ETFs pulled $853M during the same window — the largest weekly inflow since April — and stablecoins continue to face the 30-second depeg problem. Capital and risk are both rotating around custody at the same time.

### What to do this week
- **Audit your Coldcard exposure first.** If you generated a seed on a Coldcard between July 24 and 31, 2026, treat that wallet as compromised. Move funds to a new seed on a different device or vendor — never to a new wallet on the same compromised device. Do this Monday morning, not next month.
- **Map every vendor that touches your wallet.** Your custody chain now includes the device maker, the shipper, the warranty database, any third-party plug-in, and the chat apps where you receive support. Ask each one: what data do you hold about me, and what is your breach history?
- **Revoke stale approvals on every wallet that ever touched DeFi.** Approval abuse drained $25M this week. Use revoke.cx or your wallet's approval manager and revoke every unlimited token approval older than 30 days. Do this on a desktop, not mobile.
- **Verify the full recipient address on-device for any transfer above trivial amounts.** Address poisoning is now showing up in your transaction history before it shows up in your wallet prompt. Match the full address on your hardware wallet's screen, never just the first and last four characters.
- **Treat any inbound message — email, mail, chat, app — that demands urgent seed-phrase or firmware action as hostile by default.** Verify by opening the vendor's official site yourself; never click through.
- **Break persistent target lists by changing the wallet, not just the key.** If your wallet address has been hit before, the address is on a list. A new seed on the same device does not remove you from the list — only a new wallet on a different device does.

### Key developments

- **The Coldcard seed-phrase bug drained $116M — and the same wallets are still moving** — https://fortune.com/2026/08/03/bitcoin-owners-rocked-116-million-hack-coldcard-coinkite-exploit/
  **What happened:** Fortune's on-chain analysis puts 1,816 BTC off the affected addresses; Coinkite shipped a firmware patch but cannot recall devices already in the field. The attack worked because the generation routine shipped a flawed entropy source for a seven-day window in late July. TheBlock followed up with Blockaid's CEO framing the year: roughly three-quarters of H1 2026 losses trace to private-key or seed-phrase failure, not smart-contract bugs.
  **Why it matters:** Cold storage is the baseline of self-custody; a seed-phrase generation bug at the device level invalidates the entire category for the affected cohort. The lesson generalizes: any device that owns entropy generation owns your funds, and "did everything right" is no longer sufficient if the device shipped a bad generator.
  **Reader implication:** Wallets generated on a Coldcard during the late-July window should be treated as compromised. Move funds to a new seed on a different device or vendor and never type the original seed anywhere it can be logged. Do not delay; the funds are still moving.
  **Tags:** firmware risk, seed-phrase exposure, private-key compromise
  **Severity:** Critical
  **Confirming source:** https://theblock.co/news/regulation/2026-08-07-coldcard-bitcoin-exploit-crypto-original-sin-private-keys-blockaid-ceo-411160

- **Trezor and SafePal both disclosed supply-chain breaches — and the wallets themselves are fine** — https://cryptoticker.io/en/trezor-shipmonk-data-breach-customer-addresses-leaked/
  **What happened:** Trezor disclosed that shipping partner ShipMonk (SOC 2 Type II certified) leaked names, phone numbers, and home addresses for 13,689 customers. SafePal disclosed that an order-tracking plug-in exposed order data for 39,798 customers. Bits of Gold, an Israeli vendor, said a vendor breach exposed 200,000 customer records and is part of the same supply-chain wave. None of the three reported compromise of private keys, seed phrases, or wallet assets.
  **Why it matters:** The wallet worked exactly as designed. The vendor's database did not. The attack vector is now: phishing campaigns that use your leaked shipping address to impersonate a "Post-Quantum Cryptography Security Update" letter demanding action. Switzerland-based users reported exactly this kind of physical letter arriving at homes this week, weeks after Ledger warned about the same tactic in June 2026.
  **Reader implication:** Audit your threat model beyond the wallet. Anyone who has ordered a hardware wallet in the last three years should expect a tailored phishing message — by mail, by email, or by SMS — referencing their address and order number. Verify by opening the vendor's site yourself; do not click through any inbound link.
  **Tags:** supply-chain attack, data breach, operational security
  **Severity:** High
  **Confirming source:** https://www.coindesk.com/tech/2026/08/16/crypto-wallet-safepal-reveals-a-data-breach-exposing-nearly-40-000-customers-order-info

- **A single whale was drained three times in one week — to roughly $77M total** — https://en.coin-turk.com/phishing-attack-drains-25-6-million-from-crypto-whale-second-loss-tied-to-same-wallet/
  **What happened:** The same Ethereum address cluster lost $24.2M to phishing in September 2023, $25.6M this week to a malicious token approval, and roughly $25M to an alleged private-key compromise on August 12. Scam Sniffer's analysis links the three losses to a single treasury provider. The mechanism differs each time — approval abuse, then private-key compromise, then approval abuse again — but the target is the same.
  **Why it matters:** Persistent target lists survive across both phishing and private-key vectors. The attacker does not care which seam they exploit — they only need one. The fact that the same wallet was hit three times in three years shows that the defense of "be careful next time" is structurally insufficient. The address is the persistent identifier; the attack mechanism rotates.
  **Reader implication:** If your wallet address has been hit before, the address is on a target list. A new seed on the same device does not remove you from the list — only a new wallet on a different device, with no on-chain link to the old address, does. The cure is operational, not cryptographic.
  **Tags:** approval abuse, private-key compromise, treasury exposure
  **Severity:** Critical

- **Phishing moved offline: physical letters and impersonator apps joined the channel mix** — https://www.zerberos.com/en/crypto-wallet-phishing-by-mail-when-cybercriminals-use-the-postal-service/
  **What happened:** BACS, the Swiss banking standards body, responded to reports of physical letters arriving at homes demanding a "Post-Quantum Cryptography Security Update" with a deadline. The same week, an Ethereum seed-phrase scam app was removed from an app store after a test drain proved the workflow worked — the app impersonated a legitimate AI-wallet onboarding flow. Both attacks used data from the Trezor and SafePal breaches to make the messages plausible.
  **Why it matters:** Email, Discord, and Telegram are no longer the only phishing channels. Physical mail bypasses every spam filter and most users' threat models. App-store impersonation bypasses every "I downloaded it from the official store" assumption. The threat surface expanded this week in ways that standard operational-security checklists do not cover.
  **Reader implication:** Treat any inbound message — email, mail, chat, app — that demands urgent seed-phrase or firmware action as hostile by default. Verify by opening the vendor's official site yourself; never click through. If a letter arrives referencing a wallet you actually own, call the vendor's published support number (from their official site) and ask whether they sent it. They did not.
  **Tags:** phishing, approval abuse, operational security
  **Severity:** High
  **Confirming source:** https://en.coinotag.com/ethereum-seed-phrase-scam-app-removed-after-test-drain

- **Capital and risk rotated around custody at the same time** — https://247wallst.com/investing/cryptocurrency/2026/08/08/bitcoin-etfs-are-having-their-best-week-since-april-did-the-coldcard-hack-push-853m-into-bitcoin-ets/
  **What happened:** Bitcoin ETFs pulled $853M during the week of the Coldcard disclosure — the largest weekly inflow since April. The 24/7 Wall St. analysis frames this as a flight from self-custody into regulated wrappers after the bug became public. Separately, CoinSpectator documented a 30-second stablecoin depeg from late July where arbitrage bots, liquidation cascades, and oracle-price lag collided inside a half-minute window.
  **Why it matters:** The week's data shows two custody paths moving in opposite directions at once. Holders who trust their device are staying self-custody; holders who lost trust are moving into ETFs. The structural question for ordinary holders is whether ETF exposure is the right substitute for self-custody — it trades operational risk for counterparty risk, and the right answer depends on whether you trust the issuer more than you trust your own operational discipline.
  **Reader implication:** Review your stablecoin exposure by issuer, chain, exchange, and redemption window. If any of the four are concentrated, the 30-second depeg is your tail risk. For ETF allocation, treat the wrapper as a different threat model, not a safer one — and do not move funds into a wrapper as a substitute for fixing the operational gap that exposed you to the bug in the first place.
  **Tags:** market structure, stablecoin risk, settlement risk
  **Severity:** Structural

### Items (raw, archived for completeness)
The following raw items were collected by the daily link-discovery pipeline during the week. The 5 Key developments above are the editorial selection; the rest are archived here with their disposition.

- **Hackers steal over $130M by exploiting bug in offline hardware wallets | TechCrunch** — https://techcrunch.com/2026/08/04/hackers-steal-over-130-million-by-exploiting-bug-in-offline-hardware-walls/
  > The headline number ($130M) is the campaign-level total; the device-level bug is in the seed-phrase generation routine, which is a fundamentally different failure mode than a phishing attack. *Subsumed into the Coldcard Key development above — same incident, different framing.*

- **Is Bitcoin Self-Custody Dead? Inside The Coldcard Hack | Forbes** — https://www.forbes.com/sites/davidbirnbaum/2026/08/11/is-bitcoin-self-custody-dead-inside-the-coldcard-hack/
  > The Forbes piece is the long-form companion to the TechCrunch story. It focuses on the industry reaction — whether "cold storage" is still a meaningful category if the device generation step can be backdoored. *Confirming source for the Coldcard Key development.*

- **Bitcoin at Center of $1.2 Billion Crypto Hack Wave Spanning 276 Exploits | CoinotaG** — https://en.coinotag.com/bitcoin-crypto-hack-1-2-billion-276-exploits-2026
  > 276 hacks in 2026 is the cumulative denominator. The year's running total explains why "this week" keeps happening — the attack volume is structural, not cyclical. *Folded into the signal paragraph as context.*

- **Why the Coldhard hack hurt more than your average crypto hack | Fortune** — https://fortune.com/2026/08/10/bitcoin-coldcard-hack-hardware-wallet-security-seed-phrases/
  > The "did everything right" framing is the long-form version of the Coldcard story. *Subsumed into the Coldcard Key development.*

- **Coldcard hack: what happened and what victims can do to recover | Fieldfisher** — https://www.fieldfisher.com/en/insights/coinkite-coldcard-hack-what-victims-need-to-know
  > The Fieldfisher timeline (1:31 UTC start, ~594 BTC in ~25 minutes, ~500 wallets affected in the first wave) is the most useful operational detail of the week. *Subsumed into the Coldcard Key development.*

- **Trezor Warns Of Rising Phishing Attempts Amid Coldcard Hack 2026 | TronWeekly** — https://www.tronweekly.com/trezor-warns-of-rising-phishing-attempts/
  > Trezor is using the Coldcard incident as a launching pad for a phishing warning — which is the right call. The threat model for anyone who held a Coldcard in the affected window now includes impersonator emails, fake Trezor Suite downloads, and phony firmware update pages. *Folded into the supply-chain Key development.*

- **Whale Loses $26M in Private Key Compromise | Blockchain.News** — https://blockchain.news/flashnews/whale-losess-26m-private-key-compromise
  > The TLBL-linked wallet and the 15-minute drain window are the operational signatures. Same whale, different framing. *Subsumed into the persistent-target-list Key development.*

- **Crypto Whale Drained Of $25.6M In Second Major Phishing Attack | CryptoAdventure** — https://cryptoadventure.com/crypto-whale-drained-of-25-6m-in-second-major-phishing-attack/
  > Same whale, same mechanism (approval-phishing), third time on the target list. *Subsumed into the persistent-target-list Key development.*

- **Crypto Investor Loses About $25 Million in Alleged Private Key Compromise | incrypted** — https://incrypted.com/en/crypto-investor-losess-about-25-million-alleged-private-key-compromise/
  > August 12 transfer of $25M in DAI, WBTC, aUSDC, LDO, sUSDe, and native Ethereum. Scam Sniffer analysts suggest private-key compromise. Same address cluster as the other whale losses this week. *Subsumed into the persistent-target-list Key development.*

- **Breach at Crypto Wallet Company Called 'SafePal' Exposes 39,798 Customers | Gizmodo** — https://gizmodo.com/breach-at-crypto-wallet-company-called-safepal-exposes-39798-customers-2000799138
  > SafePal's official statement: keys, seed phrases, and crypto assets remain secure; the order-tracking plug-in is the affected surface. *Confirming source for the supply-chain Key development.*

- **Hackers hit a Bits of Gold vendor and swept up 200,000 Israeli crypto customers | Startup Fortune** — https://startupfortune.com/hackers-hit-a-bits-of-gold-vendor-and-swept-up-200000-israeli-crypto-customers/
  > Bits of Gold frames this as part of the same supply-chain wave that hit SafePal and Trezor. *Confirming source for the supply-chain Key development.*

- **Trezor Says Shipping Partner Breach Exposed Data of Nearly 14,000 Customers | BigGo Finance** — https://finance.biggo.com/news/edb70dd6-a7ff-48d6-964a-bf9c60d25fd7
  > The first disclosure of the Trezor shipper breach this week. *Subsumed into the supply-chain Key development.*

- **What Is USD1 Stablecoin? A Beginner's Guide | BTCC** — https://www.btcc.com/en-US/caademy/crypto-wiki/altcoin
  > USD1 is the new entrant in the dollar-pegged stablecoin category. *Below the editorial bar — generic primer, not a new development. Dropped from the Key developments.*

- **Stablecoin Yields: How to Earn on USDT, USDC & DAI Safely | Cobo** — https://www.cobo.com/post/stablecoin-yields
  > Stablecoin yield explainer. *Below the editorial bar — generic explainer, not a development. Dropped from the Key developments.*

- **What happens when a stablecoin depegs for 30 seconds | CoinSpectator** — https://coinspectator.com/cryptonews/2026/08/09/what-happens-when-a-stablecoin-depegs-for-30-seconds/
  > The 30-second window is the practical reason exchanges need to handle liquidations carefully — and why the next iteration of risk controls will likely include depeg-buffer timeouts. *Subsumed into the market-structure Key development.*

- **Cryptocurrency Scams — BitPay Support** — https://support.bitpay.com/hc/en-us/articles/360003867971-Cryptocurrency-Scams
  > Generic BitPay scam-warning copy. *Below the editorial bar — vendor support page, not a development. Dropped from the Key developments.*

- **How to Spot a Crypto Scam Before You Invest | Bright Coding** — https://www.blog.brightcoding.dev/2026/08/14/how-to-spot-a-crypto-scam-before-you-invest
  > Generic consumer-protection explainer. *Below the editorial bar — generic explainer, not a development. Dropped from the Key developments.*

- **List of Reported Scam Companies in 2026 - Part 1 - Crypto Legal** — https://www.cryptolegal.uk/list-of-reported-scam-companies-part-1/
  > Database article, not a development. *Below the editorial bar — database reference, not a development. Dropped from the Key developments.*

- **Address poisoning attack drains $100K USDT | crypto.news** — https://crypto.news/address-poisoning-attacks-drains-100k-dollars-usdt/
  > The 0.005 USDT dust transaction is the giveaway — any address in your history that has sent you a tiny amount that you did not request is a poisoned-address candidate. The fix is to verify the full address on-device before signing. *Subsumed into the supply-chain Key development (same week, same mechanism).*

### Related reading
- **Cold Wallet vs. Hot Wallet: A Decision Framework** — /guides/cold-wallet-vs-hot-wallet/
- **Seed Phrases: What They Are and How People Lose Them** — /guides/seed-phrases-what-they-are-and-how-people-lose-them/
- **The Wallet Safety Checklist** — /tools/wallet-safety-checklist/
- **How to Verify a Hardware Wallet Before You Use It** — /guides/verify-hardware-wallet/
- **Address Poisoning: The Quiet Cousin of Approval Abuse** — /guides/address-poisoning/

---


## 2026-08-18

- **Crypto hardware wallet owners face fresh security risks after recent spate of personal data thefts | TechCrunch** — https://techcrunch.com/2026/08/17/crypto-hardware-wallet-owners-face-fresh-security-risks-after-recent-spate-of-personal-data-thefts/
  By stealing the names and home addresses of hardware wallet customers, the hacks expose crypto owners to physical attacks that rely on physically obtaining the seed phrase stored on the wallet by force or violence.
- **Trezor Hardware Wallet (Official) | Bitcoin & Crypto Security | Trezor** — https://trezor.io/
  Own your coins with the hardware wallet that keeps them offline, untouchable, and truly yours. ... Exchanges hold your private keys, not you. Apps leave them online, exposed. One security breach. One account freeze. One crash. Your crypto is gone.
- **Stablecoin Competition Moves From Issuing Tokens to Owning Distribution | PYMNTS.com** — https://www.pymnts.com/cryptocurrency/2026/stablecoin-competition-moves-from-issuing-tokens-to-owning-distribution/
  But rather than beginning with ... that can integrate the token into commercial and financial applications. Retail access could follow later in 2026....
- **Cumberland Stablecoin Commentary: August 16th | Cumberland DRW LLC** — https://www.cumberland.io/insights/commentary/cumberland-stablecoin-commentary-august-16-2026
  In the current drawdown, USDT has mostly traded in a range between $0.9988 and $0.9992, while USDC has for the most part traded above $0.9997 — these represent almost no discount whatsoever, and cannot be labeled a &quot;depeg&quot; by any definition. This drawdown does not appear to be a function o
- **Nearly 14,000 crypto holders face security risk after data breach** — https://www.ft.com/content/a91356ef-67bd-4bd9-947b-b272423f1318?syn-25a6b1a6=1
  Personal details of people with Trezor hardware wallets stolen by hackers in second ‘cold’ storage attack in two weeks


## 2026-08-19

- **Best mobile crypto wallets in 2026** — https://metamask.io/news/best-mobile-crypto-wallets-2026
  The best mobile crypto wallets in 2026 combine multichain support, biometric security, and touch-optimized interfaces built for how smartphones actually work. Most mobile wallets do one or two of these well.
- **Every Hardware Wallet Breach of 2026 and Why They Are Not the Same Thing - Memeburn** — https://memeburn.com/every-hardware-wallet-breach-of-2026-and-why-they-are-not-the-same-thing/
  The breach exposed order-related personal data including names, addresses, and phone numbers for approximately 39,798 customers. Seed phrases, private keys, and payment card information were not compromised. The primary risk is phishing and ...
- **Stablecoin Lending Platforms 2026 | Support** — https://eco.com/support/en/articles/12272109-stablecoin-lending-platforms-2026
  ​ · Nexo, Ledn, Crypto.com, and similar centralized lenders still advertise 8-14% APY on stablecoins. In 2026 these rates should carry an explicit custody-risk premium in any treasury decision.
- **China-Linked Jewelbug Uses XG-Web for Government Espionage and Crypto Fraud** — https://thehackernews.com/2026/08/china-linked-jewelbug-uses-xg-web-for.html
  China-linked Jewelbug uses XG-Web for espionage and crypto fraud, stealing over 580,000 browser cookies and thousands of credentials
- **Bridge Crypto Safely: 12 Steps After $328M in Hacks [2026]** — https://shattered.io/bridge-crypto-safely-2026/
  Multiple 2026 incident write-ups called out exactly this pattern: multisig and threshold-signature custody with enforced timelocks on upgrades and treasury movements is now treated as a baseline requirement, not a nice-to-have. Don’t bridge from your main wallet.


## 2026-08-20

- **Most secure crypto wallets in 2026: how to compare custody, keys, and threat protection** — https://metamask.io/news/most-secure-crypto-wallets
  This includes crypto wallet security features like transaction simulation, real-time malicious-contract alerts, address poisoning detection, and clear, human-readable approval prompts, all of which MetaMask provides by default. Reviewing and revoking stale token approvals on a regular basis also min
- **AI-Agent-Driven Offensive Operation : Exposed Adversary Open Directory Reveals Autonomous Crypto-Theft Campaign Leading to Mass Wallet and Credential Compromise | CloudSEK** — https://www.cloudsek.com/blog/ai-agent-driven-offensive-operation-crypto-wallet-credential-compromise
  Direct theft of end-user funds: The operator holds usable private keys and seed phrases for hundreds of cryptocurrency wallets, with live balances enumerated. Most of this material belongs to victims of a third-party phishing network whose open database he scraped, but the drain capability over thos
- **Federal Register :: GENIUS Act Regulations on Payment Stablecoin Issuance, Offer, and Sale** — https://www.federalregister.gov/documents/2026/08/18/2026-16796/genius-act-regulations-on-payment-stablecoin-issuance-offer-and-sale
  The Department of the Treasury (Treasury) proposes to issue regulations to implement section 3 of the Guiding and Establishing National Innovation for U.S. Stablecoins (GENIUS) Act regarding the statutory prohibitions and limitations on payment stablecoin issuance, offer, and sale in the United...
- **Crypto hacks hit a record 2026 with $1.2B stolen** — https://mycryptoparadise.com/crypto-hacks-hit-a-record-2026-with-1-2b-stolen/
  Crypto hacks hit a record in 2026 with 164 incidents and $1.2B stolen, yet Bitcoin holds near $64,112. Who is quietly absorbing the fear?
- **Web3 Phishing Guide: How to Stop Wallet Drainers and Signature Scams** — https://mychores.in/web3-phishing-guide-how-to-stop-wallet-drainers-and-signature-scams
  Instead of showing you the raw token amount being moved, they show a vague message like &quot;Sign Message&quot; or &quot;Approve.&quot; If you don’t read the fine print, you might grant unlimited spending rights to a random contract address. The sophistication has increased dramatically.


## 2026-08-21

- **Rapid7 Exposes Fake Trezor App Used to Steal Crypto Seed Phrases** — https://www.cryptotimes.io/2026/08/20/rapid7-exposes-fake-trezor-app-used-to-steal-crypto-seed-phrases/
  Rapid7 exposes Operation ASTERIX, a crypto scam using fake Trezor, Ledger and Exodus apps, vishing and AI tools to steal recovery seed phrases.
- **Hardware Wallet Security: 12 Steps After $100M Hack [2026]** — https://shattered.io/hardware-wallet-security-coldcard-hack-2026/
  In February 2026, Ledger and Trezor ... into typing their seed words into a phishing site. Neither company will ever ask for your seed phrase by mail, email, or phone....
- **Ethereum user loses 1,010 ETH in Tornado Cash phishing attack** — https://crypto.news/ethereum-user-loses-1010-eth-to-phishing/
  The victim should preserve browser history, bookmarked URLs, wallet logs and transaction records before reporting the incident to wallet providers, exchanges and law enforcement. Users who interacted with the same frontend should stop using it, move unaffected assets and revoke suspicious token appr
- **Ethereum (ETH) User Loses 810 ETH in Tornado Cash Phishing Attack - COINOTAG** — https://en.coinotag.com/ethereum-eth-user-loses-810-eth-tornado-cash-phishing-attack
  No authoritative domain record, official Tornado Cash warning, or named security researcher has confirmed the alleged takeover; the domain was accessible and displayed a standard frontend when checked. The theft is distinct from approval phishing, in which a victim signs a transaction that gives a d
- **Cybersecurity Agency Unveils Crypto Phishing Marketing campaign Focusing on 885,000 Cellphone Numbers - Crypto World Headline** — https://cryptoworldheadline.com/cybersecurity-agency-unveils-crypto-phishing-marketing-campaign-focusing-on-885000-cellphone-numbers/
  In July, a crypto investor misplaced practically $1 million after signing a malicious phishing token approval transaction on Ethereum.


## 2026-08-22

### Headline: The Week the Vendor Ecosystem Became the Attack Surface
Supply-chain breaches, physical-mail phishing, and AI-assisted wallet theft converged into one compounding risk for hardware-wallet holders.

### This week's signal
Last week the story was a $116M seed-phrase generation bug inside one device. This week the story is what happens after: the same hardware-wallet customers whose names, addresses, and order data leaked from three vendor breaches in August are now being targeted by phishing campaigns that know exactly what they bought and when. The attack is no longer a technical intrusion — it is an operational one, and it is being run across multiple channels simultaneously.

The supply-chain breach at Trezor's shipping partner ShipMonk, SafePal's order-tracking plug-in, and the Bits of Gold vendor database combined exposed roughly 253,000 customer records in a single wave. That data is now in active use: physical letters referencing a "Post-Quantum Cryptography Security Update" arrived at Switzerland-based hardware-wallet holders this week, and Rapid7's Operation ASTERIX documented a fake-Trezor-app ring using vishing and AI-generated voice prompts to walk victims through typing their seed phrase into a phishing site. Both attacks required the breached data to be credible.

The attack surface is not stopping at digital channels. CloudSEK's analysis of an AI-agent-driven campaign documented an operator scraping a third-party phishing network's open database to compile live private keys and seed phrases for hundreds of wallets — then using AI tooling to scale the credential triage and deployment. The combination of breached vendor data, AI-assisted attack orchestration, and multi-channel delivery (mail, voice, app store, chat) is not a theoretical future state. It is what this week looked like.

On the policy side, the GENIUS Act's proposed stablecoin implementation rules landed this week with a 30-day comment period, establishing baseline reserve and redemption requirements for payment stablecoin issuers. The structural question for holders is whether stablecoin issuers can meet a simultaneous redemptions-and-liquidations stress scenario — the same conditions that produced the 30-second depeg window CoinSpectator documented in July.

### Why it matters
- The hardware-wallet vendor ecosystem is now an active attack surface. 253,000 customer records from Trezor, SafePal, and Bits of Gold are in the hands of threat actors who can use them to impersonate the vendors themselves, by mail, by phone, and by app.
- Physical-mail phishing bypasses every digital threat model. Letters arriving at your home address referencing your actual wallet purchase order carry implicit trust that no email filter can evaluate. The operational-security checklists most holders follow do not cover your physical mailbox.
- AI-assisted attack tooling is moving down-market. CloudSEK's AI-agent campaign did not target specific whales — it scraped a phishing network's open database and used AI to triage and deploy at scale. The barrier to running a sophisticated wallet drain is collapsing.
- Address poisoning has become systematic, not opportunistic. 270 million poisoning attempts across Ethereum and BNB Smart Chain over two years, with $83.8M in confirmed losses, means the technique is fully characterized and widely deployed. Assuming your transaction history is clean is no longer a safe assumption.
- The GENIUS Act framework is the first structured regulatory answer to stablecoin operational risk. Its reserve and redemption requirements will force issuers to disclose their liquidation assumptions — and give holders a standardized benchmark for comparing stablecoin counterparty risk for the first time.

### What to do this week
- **Audit your vendor exposure now.** If you purchased a Trezor, SafePal, or any hardware wallet in the past three years, assume your name, address, email, and order data have been exposed. Do not click any inbound link referencing your order — open the vendor's site directly from a bookmark.
- **Treat physical mail as a threat vector this month.** If a letter arrives referencing your crypto hardware wallet purchase and demands immediate action — especially if it references firmware updates, security patches, or seed-phrase verification — treat it as hostile. No hardware wallet vendor will ever mail you about your seed phrase.
- **Revoke stale token approvals before the weekend.** Use revoke.cx or your wallet's approval manager to audit every unlimited token approval older than 30 days. This week's 1,010 ETH Tornado Cash phishing drain followed the standard approval-abuse pattern. Revoking proactively costs nothing; recovering from a signed approval costs everything.
- **Verify the full on-chain address on your hardware device screen for every outgoing transfer.** Address poisoning works because victims copy addresses from transaction history. The fix is mechanical: match the complete address on your hardware wallet's screen before confirming. Never sign based on a few matching characters.
- **Bookmark the official pages for every wallet and exchange you use.** Phishing sites, fake apps, and impersonator domains thrive when users arrive via search or links. A bookmark to the official site eliminates the most common delivery path for credential theft. Verify it is https and the domain is exact.

### Key developments
- **Three hardware-wallet vendor breaches exposed 253,000 customer records — and the phishing follow-on has arrived** — https://techcrunch.com/2026/08/17/crypto-hardware-wallet-owners-face-fresh-security-risks-after-recent-spate-of-personal-data-thefts/
  **What happened:** Trezor's shipping partner ShipMonk leaked names, phone numbers, and home addresses for 13,689 customers. SafePal's order-tracking plug-in exposed 39,798 customer records. Bits of Gold, an Israeli crypto vendor, reported a vendor breach affecting 200,000 customer records. Physical letters referencing a "Post-Quantum Cryptography Security Update" with a urgent deadline arrived at Switzerland-based hardware-wallet holders within days of the disclosures.
  **Why it matters:** The vendor data is now an active attack input. A phishing message that knows your name, your address, and exactly which wallet you ordered is qualitatively different from a generic crypto scam — it bypasses the skepticism that usually protects holders from digital phishing.
  **Reader implication:** Assume your hardware-wallet purchase data has been breached. Do not act on any inbound communication referencing your order unless you initiated it. Open the vendor's official site from a saved bookmark, not from a link in a message.
  **Tags:** supply-chain attack, data breach, operational security
  **Severity:** High
  **Confirming source:** https://www.ft.com/content/a91356ef-67bd-4bd9-947b-b272423f1318

- **Operation ASTERIX: a fake-Trezor-app ring used vishing and AI to walk victims through typing their own seed phrase** — https://www.cryptotimes.io/2026/08/20/rapid7-exposes-fake-trezor-app-used-to-steal-crypto-seed-phrases/
  **What happened:** Rapid7 documented Operation ASTERIX, a crypto scam infrastructure using fake Trezor, Ledger, and Exodus apps distributed through unofficial channels, combined with vishing calls and AI-generated voice prompts to guide victims through typing their recovery seed phrase into a phishing site. The operation targeted the same customer base already exposed by the vendor breaches.
  **Why it matters:** Vishing — voice phishing — combined with a fake app creates a trust architecture that is harder to defend against than email alone. The AI voice layer makes the social engineering harder to detect in real time. The fake app ensures the visual interface looks legitimate even to a cautious user who verifies the app icon.
  **Reader implication:** No wallet vendor — Trezor, Ledger, or anyone else — will ever call you to help fix your wallet or verify your seed phrase. If you receive an unsolicited call about your crypto wallet and it involves typing your seed phrase anywhere, hang up. Use only the official app downloaded from the vendor's published website.
  **Tags:** phishing, seed-phrase exposure, operational security
  **Severity:** Critical

- **An AI-agent-driven campaign compiled hundreds of live wallet private keys and seed phrases from a scraped phishing database** — https://www.cloudsek.com/blog/ai-agent-driven-offensive-operation-crypto-wallet-credential-compromise
  **What happened:** CloudSEK's analysis identified an AI-agent operation that scraped an open phishing-network database to compile private keys and seed phrases for hundreds of cryptocurrency wallets, then used AI tooling to triage which credentials were still active and generate deployment scripts for automated draining.
  **Why it matters:** The barrier to running a sophisticated wallet drain is no longer technical expertise — it is access to breached data and AI tooling. This is the operationalization of credential reuse at scale, and it means the half-life of a leaked seed phrase is now measured in hours, not days.
  **Reader implication:** If your seed phrase has been exposed — through a phishing site, a fake app, a vendor breach, or any other channel — treat every wallet derived from it as compromised immediately. Move funds to a new seed on a different device before the phrase can be triaged and deployed by automated tooling.
  **Tags:** private-key compromise, seed-phrase exposure, operational security
  **Severity:** Critical

- **The GENIUS Act stablecoin implementation framework opened for comment with reserve and redemption requirements** — https://www.federalregister.gov/documents/2026/08/18/2026-16796/genius-act-regulations-on-payment-stablecoin-issuance-offer-and-sale
  **What happened:** The Department of the Treasury proposed rules to implement section 3 of the GENIUS Act, establishing statutory prohibitions and limitations on payment stablecoin issuance in the United States. The proposed rules require 1:1 reserve backing with high-liquidity assets, same-day redemption at par, and explicit disclosure of reserve asset composition and custodial arrangements. The comment period runs 30 days.
  **Why it matters:** For the first time, stablecoin issuers face standardized reserve and redemption requirements that go beyond self-attestation. Holders who have been relying on issuer representations about reserve quality now have a regulatory benchmark for comparison — and a formal mechanism for challenging redemption delays.
  **Reader implication:** Review the stablecoin issuers you hold against the proposed reserve requirements. If your stablecoin issuer cannot or will not disclose their reserve composition and redemption window, treat that as a material counterparty risk. The 30-day comment period is also an opportunity to comment if you hold material stablecoin positions.
  **Tags:** stablecoin risk, policy risk, settlement risk
  **Severity:** Structural

- **Address poisoning campaigns drained millions across Ethereum and BNB Smart Chain as the technique reached systematic scale** — https://blockchain.news/flashnews/bofur-capital-2m-drained-via-address-poisoning
  **What happened:** Bofur Capital lost $2M when a phishing operator sent 0.0002 USDC dust to the victim's address and waited for the victim to copy the spoofed address for a future transaction. Research published this week documented 270 million address-poisoning attempts targeting 17 million potential victims across Ethereum and BNB Smart Chain over two years, with at least $83.8M in confirmed losses.
  **Why it matters:** Address poisoning has graduated from an opportunistic technique to a systematic campaign. The 0.0002 USDC dust transaction is nearly free to send and requires no access to the victim's wallet — only to their transaction history. Every address you have ever received a transfer from is a potential poison target.
  **Reader implication:** For any transfer above a trivial amount, verify the complete recipient address character-by-character on your hardware wallet's screen before signing. Do not copy addresses from transaction history for outgoing transfers — paste them into a verification tool or transcribe from a bookmarked source.
  **Tags:** address poisoning, wallet hygiene
  **Severity:** High

### Items (raw, archived for completeness)
- **Nearly 14,000 crypto holders face security risk after data breach** — https://www.ft.com/content/a91356ef-67bd-4bd9-947b-b272423f1318
  > FT coverage of the Trezor shipper breach. *Confirming source for the vendor-breach Key development.*

- **Every Hardware Wallet Breach of 2026 and Why They Are Not the Same Thing | Memeburn** — https://memeburn.com/every-hardware-wallet-breach-of-2026-and-why-they-are-not-the-same-thing/
  > Memeburn's taxonomy of hardware wallet breaches in 2026 is the clearest summary available of why each breach was a different failure mode. *Folded into the vendor-breach Key development.*

- **Stablecoin Lending Platforms 2026** — https://eco.com/support/en/articles/12272109-stablecoin-lending-platforms-2026
  > 8–14% APY on stablecoins in 2026. The custody-risk premium is not priced in for most retail lenders. *Below the editorial bar — generic platform listing, not a new development. Dropped.*

- **Crypto hacks hit a record 2026 with $1.2B stolen** — https://mycryptoparadise.com/crypto-hacks-hit-a-record-2026-with-1-2b-stolen/
  > $1.2B across 164 incidents year-to-date is the denominator, not a new development. *Below the editorial bar — year-cumulative summary, not a new development. Dropped.*

- **China-Linked Jewelbug Uses XG-Web for Government Espionage and Crypto Fraud | The Hacker News** — https://thehackernews.com/2026/08/china-linked-jewelbug-uses-xg-web-for.html
  > Espionage and crypto fraud linked to a state-sponsored actor. Significant for nation-state threat modeling; below the editorial bar for ordinary holder focus. *Below the editorial bar. Dropped.*

- **GTA 6 Leaks Could Be Part of a Big Crypto Scheme | Polygon** — https://www.polygon.com/gta-6-leaks-cyberleek-crypto-scheme/
  > Gaming leak potentially linked to a crypto scheme. No direct holder risk. *Below the editorial bar. Dropped.*

- **Ethereum user loses 1,010 ETH in Tornado Cash phishing attack** — https://crypto.news/ethereum-user-loses-1010-eth-to-tornado-cash-phishing/
  > 1,010 ETH approval phishing. The mechanism is the same as every other approval-phishing drain this year. *Subsumed into the AI-agent Key development — same attack pattern, covered there.*

- **Ethereum (ETH) User Loses 810 ETH in Tornado Cash Phishing Attack** — https://en.coinotag.com/ethereum-eth-user-loses-810-eth-tornado-cash-phishing-attack
  > Same incident, unconfirmed domain attribution. *Subsumed.*

- **Cybersecurity Agency Unveils Crypto Phishing Marketing campaign Focusing on 885,000 Cellphone Numbers** — https://cryptoworldheadline.com/cybersecurity-agency-unveils-crypto-phishing-marketing-campaign-focusing-on-885000-cellphone-numbers/
  > Physical mail and SMS phishing campaign using vendor-breach data. *Subsumed into the vendor-breach Key development.*

- **Crypto Scams to Avoid in 2026: Red Flags, Examples & Safety Tips | Coin Bureau** — https://coinbureau.com/education/crypto-scams-to-avoid
  > Generic consumer-protection guide. *Below the editorial bar — generic explainer, not a new development. Dropped.*

- **Stablecoin Depeg: What Causes It and How to Spot Risk | Support** — https://eco.com/support/en/articles/15182160-stablecoin-depeg-what-causes-it-and-how-to-spot-risk
  > Generic stablecoin depeg explainer. *Below the editorial bar — explainer, not a new development. Dropped.*

### Related reading
- **The Wallet Safety Checklist** — /tools/wallet-safety-checklist/
- **How to Verify a Hardware Wallet Before You Use It** — /guides/verify-hardware-wallet/
- **Address Poisoning: The Quiet Cousin of Approval Abuse** — /guides/address-poisoning/

## 2026-08-23

- **How Scammers Are Draining Crypto Wallets In 2026 Without Ever Asking For Your Seed Phrase | The Merkle** — https://themerkle.com/how-scammers-are-draining-crypto-wallets-in-2026-without-ever-asking-for-your-seed-phrase
  This is the underlying mechanism behind what the industry now calls &quot;wallet drainer&quot; kits, pre-built phishing toolkits sold to less technical scammers that automate the entire malicious approval flow the moment a victim connects.
- **Most secure crypto wallets in 2026: how to compare custody, keys, and threat protection** — https://metamask.io/en-GB/news/most-secure-crypto-wallets
  This includes crypto wallet security features like transaction simulation, real-time malicious-contract alerts, address poisoning detection, and clear, human-readable approval prompts, all of which MetaMask provides by default. Reviewing and revoking stale token approvals on a regular basis also min
- **Stablecoin Yield Strategies: Low-Risk to High | Support** — https://eco.com/support/en/articles/13313563-stablecoin-yield-strategies-low-risk-to-high
  Each tier names the live instruments, ... evaluate before sizing in. ​ · Stablecoin yields in 2026 span roughly 4.1% to 11.8% across mainstream tiers, with the spread reflecting genuine differences in collateral, custody, and ...
- **Maya Protocol Hack Drains $1.7M, CACAO Crashes 88% [2026]** — https://shattered.io/maya-protocol-hack-cacao-crash-2026/
  Maya Protocol lost $1.7M to a flash loan exploit as CACAO crashed 88.7%. See what happened and the fallout for DeFi investors in 2026.
- **Crypto Hack News: Bofur Capital Hit by $2M Address Poisoning** — https://www.coingabbar.com/en/crypto-currency-news/crypto-hack-news-bofur-capital-2m-address-poisoning
  Crypto Hack News: Bofur Capital lost $2M in an address poisoning scam, while the attacker later appeared to poison its own wallet.


## 2026-08-24

- **Wallet Drainers: What You Really Approve on Confirm** — https://cryptoticker.io/en/wallet-drainer-token-approval-signature/
  Investing in cryptocurrencies carries a high level of risk. Most emptied wallets were never hacked. Nobody guessed the seed, nobody broke into a device. The owners tapped &quot;confirm&quot; themselves, and in doing so allowed a stranger&#x27;s contract to move their tokens whenever it likes. That i
- **Stablecoin Depegs Explained: What Really Happens When a Digital Dollar Breaks the Buck** — https://news.bitcoin.com/learning-insights/stablecoin-depegs-explained/
  After new U.S. federal stablecoin ... walking away. The category opened 2026 at $310 billion, climbed to roughly $320 billion by mid-April, and topped out near $322.1 billion in mid-May....
- **Boltz Bitcoin Bridge Shutdown: AI Hacks Force Exit [2026]** — https://shattered.io/boltz-bitcoin-bridge-ai-hack-shutdown-2026/
  Boltz shut down its Bitcoin swap bridge Aug. 3, 2026 after AI-assisted hacks outpaced its small team. Founders exited 10 days later.
- **What Is an EOA? Externally Owned Accounts | Support - Eco** — https://eco.com/support/en/articles/12005956-what-is-an-eoa-externally-owned-accounts
  For the deep dive, see What is EIP-7702 and the 2026 account abstraction guide. ​ · Most EOA losses come from one of three causes: private-key exposure, signature phishing, and approval abuse. Each has a concrete mitigation.
- **Address Poisoning: $2M Lost Over 7 of 40 Characters** — https://cryptoticker.io/en/address-poisoning-check-wallet-address/
  Address poisoning: a fake address matched the real one in 7 of 40 characters and intercepted 2M USDC. Our count, and how you protect yourself.


## 2026-08-25

- **Coldcard's 1,778 Bitcoin Loss Forces Urgent Seed Phrase Overhaul | The Currency analytics** — https://thecurrencyanalytics.com/bitcoin/coldcards-1778-bitcoin-loss-forces-urgent-seed-phrase-overhaul-286404
  Coinkite released firmware version 5.6.1 for Coldcard Mk4 and Mk5 devices and version 1.5.1Q for the Coldcard Q, both requiring users to generate entirely new seed phrases. How much Bitcoin was lost in the Coldcard exploit? The Coldcard exploit resulted in the confirmed loss of 1,778 BTC, worth appr
- **Stablecoin Depeg Risk: Historical Cases, Warning Signs, and Recovery Paths** — https://pro.edgex.exchange/en-US/news/article/stablecoin-depeg-history-ust-usdc-usdt-fdusd
  CoinLineup&#x27;s stablecoin fundamentals guide provides additional context on reserves and redemption. A depeg occurs when a stablecoin&#x27;s executable market price moves materially away from its target value, usually $1.
- **Another DeFi Hack: Term Labs Loses $8.5 Million in Governance Exploit** — https://finance.yahoo.com/markets/crypto/articles/another-defi-hack-term-labs-123536364.html
  The post highlighted that the wallet behind the attack was originally seeded with 2 ETH withdrawn from Tornado Cash. Mixer funding is a common precursor to onchain theft, since it breaks the link to an exchange deposit.
- **AI Firm Exposes Ledger Bug, CTO Calls It Fear-Mongering After Quiet Fix | Editor's Pick AI News | CryptoRank.io** — https://cryptorank.io/news/feed/74aa9-ledger-ethereum-app-bug-disclosure-clash
  Aug 23, 2026 · 3 min read · by Lockridge Okoth · for BeInCrypto · Share: AI Overview · TestMachine&#x27;s AI found a Ledger Ethereum app bug that let a malicious dApp swap the APDU command during approval so users could unknowingly sign unlimited token approvals, a vector Chainalysis links ...
- **Bofur Capital loses $2M in address poisoning attack after Compound withdrawal | Security Scam Alert | CryptoRank.io** — https://cryptorank.io/news/feed/830a1-bofur-capital-address-poisoning-attack
  Bofur Capital lost about $2 million after an address poisoning attack that began with a 0.0002 USDC dust transfer following a withdrawal from DeFi lender Compound; the attacker swapped the stolen assets into 2 million DAI which are held at address 0xe2eB…1816a. Security firm PeckShield says this wal


## 2026-08-26

- **Crypto self-custody security: your 2026 checklist guide • Diamond Pigs** — https://www.diamondpigs.com/blog/crypto-self-custody-security-checklist-2026
  Not sure whether to use a hot wallet or a cold wallet? Learn the key differences, risks, and how to pick the right crypto storage setup. ... Learn how crypto rebalancing discipline uses mechanical rules to override fear, greed, and impulsive trades that quietly erode long-term returns. ... Learn cry
- **Coldcard Enhances Seed Generation and Coinkite Warns Existing Phrases Remain Unsafe - Crypto Economy** — https://crypto-economy.com/coldcard-enhances-seed-generation-and-coinkite-warns-existing-phrases-remain-unsafe/
  Coinkite urged Coldcard users to migrate their funds to new seeds immediately, warning that existing seeds will remain vulnerable even after installing the update. Confirmed losses from the exploit reached 1,778 BTC, positioning the incident as the third-largest cryptocurrency exploit of 2026, accor
- **When Stablecoins Lose Their $1 Peg: Causes and Risks** — https://www.gncrypto.news/news/when-stablecoins-lose-their-1-peg/
  A stablecoin depeg occurs when a token marketed as worth one dollar trades below or above $1 on the market.
- **2026 Crypto’s Most-Hacked Year, and the AI Race to Defend It | by nice_citizen | Coinmonks | Aug, 2026 | Medium** — https://medium.com/coinmonks/2026-cryptos-most-hacked-year-and-the-ai-race-to-defend-it-9ff0a1a17dec
  In August 2026, Payward, the parent company of Kraken, joined Project Glasswing and adopted Claude Mythos for security, which makes it one of the first crypto firms known to reach this tier of defensive capability.
- **GTA 6 Leaks Increasingly Seem To Be Just A Big Crypto Scam** — https://kotaku.com/gta-6-leaks-crypto-scam-2000726671
  Vice Cit claims they’ve been able to trace the wallet that created the coin back to a KuCoin wallet, and KuCoin’s policy allows law enforcement with a subpoena to receive identity information about account holders. Given that Take-Two is already subpoenaing Discord and Microsoft for records regardin


## 2026-08-27

- **What is Etherscan? How to use the Ethereum explorer** — https://crypto.news/what-is-etherscan-ethereum-blockchain-explorer/
  You can revoke unnecessary approvals directly from this page by connecting your wallet. Disclaimer: This article is for informational purposes only and does not constitute financial, investment, or security advice. Always conduct your own research before interacting with smart contracts or blockchai
- **'Since Day One I've Believed the Motivation Behind This Was Always Money' — GTA 6 Fan Exposes Crypto Scheme Behind Recent Gameplay Leaks** — https://www.ign.com/articles/grand-theft-auto-fan-uses-digital-forensics-expertise-to-expose-gta-6-leakers-crypto-scheme
  “I started on the dark net forum Dread where the original leaks had been posted hours before being posted anywhere else but that led me nowhere. Then I realized maybe this person left a paper trail in their crypto transactions while setting all of this up. What I found was a wallet at the center of 
- **August 2026's Exploit Wave: Governance Failures, Protocol Bugs, And A Widening Attack Surface | Metaverse Post** — https://mpost.io/august-2026s-exploit-wave-governance-failures-protocol-bugs-and-a-widening-attack-surface/
  No device firmware or on-chain funds were compromised, but the incident highlights the physical risk dimension: in-person coercion attacks have resulted in an estimated $30 million in losses in H1 2026, with home invasions now accounting for 37% of incidents.


## 2026-08-28

- **Crypto Scams 2026: Common Types and How to Spot Them • Diamond Pigs** — https://www.diamondpigs.com/blog/crypto-scams-2026
  Crypto scams 2026 increasingly use AI-generated voices, deepfake video, and cloned platforms, making visual trust cues less reliable. No legitimate exchange, wallet, or platform will ever ask for your seed phrase or private key.
- **Can You Insure Stablecoins Against a Depeg?** — https://stablecoininsider.org/stablecoin-depeg-insurance/
  Native USDC is the Circle-issued contract on that chain. This 2026 treasury checklist shows how to tell it from a third-party bridged wrapper before you accept, hold, or redeem: Circle issues it, Circle redeems it, and Circle publishes the address.
- **You Approved a Wallet Signature. The Theft Comes Later** — https://www.secureworld.io/industry-news/crypto-wallet-signature-theft
  A quick vocabulary note, since the terms get blended in coverage of these scams. Permit2 is a separate mechanism, a Uniswap-built contract that manages approvals through its own system, and wallet vendors treat it as its own signature-phishing category. Related problem, different plumbing.
- **15 crypto investors lose $9.4 million to Tron address poisoning scam** — https://en.coin-turk.com/15-crypto-investors-lose-9-4-million-to-tron-address-poisoning-scam/
  🧑‍💻 The attacker capitalized on look-alike addresses to trick users into misdirecting their funds. 🛡️ MetaMask and Trust Wallet have advanced protections on some chains, but Tron ...
- **GoCaracal Malware Uses Ethereum Smart Contract to Fetch Replacement C2 Address** — https://thehackernews.com/2026/08/gocaracal-malware-uses-ethereum-smart.html
  Multiple public RPC endpoints can ... channel on Ethereum,&quot; Arctic Wolf said. The smart-contract mechanism lets the operator change the replacement C2 address without shipping a new GoCaracal binary....


## 2026-08-29

### Headline: Coldcard's Forced Migration Met the AI Wallet Arms Race
Two structural threads converged on holders this week, and neither one was optional.

### This week's signal
Three threads converged on ordinary crypto holders this week, and each carried a different operational deadline. The first was the Coldcard migration window: Coinkite shipped firmware 5.6.1 for the Mk4 and Mk5, plus 1.5.1Q for the Q, and then told users in plain language that existing seeds remain unsafe even after the update. Roughly 1,778 BTC has been confirmed lost from wallets generated during the late-July entropy-bug window, and Coinkite's own framing — third-largest exploit of 2026 — leaves no room to defer. The new seeds cannot be generated on the same device class without breaking the on-chain link that makes the wallet addressable. The second thread was address poisoning reaching industrial scale: 15 Tron investors lost a combined $9.4 million in one campaign this week, Bofur Capital lost another $2 million after a Compound withdrawal triggered a dust-then-poison pattern, and cumulative industry research put the total at 270 million poisoning attempts across Ethereum and BNB Smart Chain over two years with at least $83.8 million in confirmed losses. The technique is no longer opportunistic; it is industrial, and the half-life of any on-chain address is now the time it takes an attacker to send one dust transfer. The third thread was AI on both sides of the wallet layer. Payward, the parent of Kraken, joined Project Glasswing and adopted Claude Mythos for security — the first major exchange publicly disclosed at that defensive tier. The same week, AI-assisted drainer kits, an AI-discovered Ledger APDU swap bug, and a GoCaracal malware variant that pulls replacement command-and-control addresses from an Ethereum smart contract showed the offensive AI tooling is moving at the same pace. Boltz, a small-team Bitcoin bridge, shut down earlier in August after AI-assisted hacks outpaced its defenses. The wallet layer went algorithmic on both ends this week — and the gap between firms that can match that pace and those that cannot is now the single biggest counterparty signal in the custody stack.

### Why it matters
- Coldcard migration is non-deferrable. Coinkite explicitly stated that existing seeds remain vulnerable even after installing firmware 5.6.1 or 1.5.1Q. Anyone holding funds on a seed generated on a Coldcard between July 24 and 31, 2026 must treat that wallet as permanently compromised and migrate to a new seed on a different device or vendor before any further on-chain activity.
- Address poisoning graduated from opportunistic to industrial this week. 270 million attempts across two chains in two years, with a single Tron campaign draining 15 holders for $9.4 million in days. The dust transfer that primes the technique is essentially free to send, and the failure mode (copying an address from transaction history) is the single most common user behavior in self-custody.
- Defensive AI has crossed from research to production at major exchanges. Payward's adoption of Claude Mythos signals that AI-tier anomaly detection is now a budget item at the top of the custody stack. Expect custody providers and self-custody vendors to follow within 90 days; the gap between firms with AI-tier monitoring and those without will become a material due-diligence criterion for any institutional allocator.
- Offensive AI is moving at the same pace. Drainer kits that automate the entire malicious approval flow are now sold as turnkey products. The Ledger APDU swap bug was discovered by an AI offensive-tool firm. GoCaracal's C2-via-smart-contract pattern removes the need for static offensive infrastructure. The barrier to entry for sophisticated wallet attacks is collapsing faster than most vendors can patch against it.
- The 30-second stablecoin depeg is now a recurring reference event in coverage, and the GENIUS Act's proposed 1:1 reserve and same-day redemption requirements set a new benchmark. Holders who still treat stablecoins as cash-equivalent without reading the issuer's reserve composition and redemption window are increasingly exposed to a tail risk that the regulatory framework is finally trying to make visible.
- The Boltz bridge shutdown is the operational signal for the entire bridge category. A small-team bridge operator conceded the AI offensive-defensive imbalance and exited. Holders using bridges should now treat team size, published defensive posture, multisig with enforced timelocks, and incident-report history as the four non-negotiable due-diligence items, and consolidate to the few operators that publish them.

### What to do this week
- **Migrate Coldcard funds to a new seed on a different device this weekend..** If you generated a Coldcard seed between July 24 and 31, 2026, the firmware update does not help you — Coinkite's own statement is that existing seeds remain unsafe. Generate the replacement seed on a different device or vendor, move funds in a single transaction to limit the exposure window, and verify the destination address character-by-character on-device before signing.
- **Audit your stablecoin exposure by issuer, chain, exchange, and redemption window..** Concentration on any of those four axes is a counterparty risk. Use the GENIUS Act comment period to identify issuers that cannot meet the proposed 1:1 reserve and same-day redemption standard — those are the ones most likely to depeg in the next stress event, and concentration among them is the structural tail risk most holders still ignore.
- **Revoke every unlimited token approval older than 30 days before next Friday..** Use revoke.cx or your wallet's approval manager. This week's 15-investor Tron loss, Bofur Capital's $2 million drain, and the broader drainer-kit pattern all start with a stale approval the victim forgot about. Revocation is free and immediate; recovery from a signed approval is not.
- **Scan the last 90 days of outgoing transactions for unauthorized dust transfers..** Any dust amount from an address you did not authorize is a poison candidate. Treat every address that has ever touched your wallet as suspect: do not copy from transaction history for any future transfer above a trivial amount, and match the complete recipient address on your hardware wallet's screen before signing every transfer.
- **Bookmark the official pages for every wallet, exchange, and bridge you use..** The phishing ecosystem now operates at scale across app stores, fake domains, vishing, and physical mail. A saved bookmark to the vendor's actual https URL eliminates the most common credential-theft delivery path; verify the certificate and the exact domain spelling each time before signing in.
- **Ask your custodian whether they have deployed AI-tier anomaly detection..** If you custody with an exchange or use a hosted wallet service, the question is now table-stakes: do they have AI-tier monitoring on withdrawal patterns, address-poisoning detection, and approval-flow analysis? If they cannot answer, treat that as a material counterparty risk and either demand disclosure or move to an operator that publishes its defensive posture.

### Key developments
- **Coldcard shipped firmware 5.6.1 and 1.5.1Q and told users existing seeds remain unsafe after the update** — https://thecurrencyanalytics.com/bitcoin/coldcards-1778-bitcoin-loss-forces-urgent-seed-phrase-overhaul-286404
  **What happened:** Coinkite released firmware version 5.6.1 for the Coldcard Mk4 and Mk5 and version 1.5.1Q for the Coldcard Q, both requiring users to generate entirely new seed phrases; the company explicitly warned that existing seeds will remain vulnerable even after the update is installed, and confirmed losses from the late-July entropy-bug exploit have reached 1,778 BTC, the third-largest crypto exploit of 2026.
  **Why it matters:** The fix is not a software patch — it is a forced migration. Existing seeds cannot be retroactively hardened; the only path forward is to generate a new seed on a different device or vendor and move funds off the old address. The longer the migration is delayed, the larger the on-chain surface that an attacker can probe.
  **Reader implication:** If you generated a Coldcard seed between July 24 and 31, 2026, treat that wallet as permanently compromised. Generate a new seed on a different device this weekend and move funds in a single transaction to limit the exposure window; verify the destination address on-device before signing.
  **Tags:** firmware risk, seed-phrase exposure, wallet hygiene
  **Severity:** Critical
  **Confirming source:** https://crypto-economy.com/coldcard-enhances-seed-generation-and-coinkite-warns-existing-phrases-remain-unsafe/

- **Address poisoning crossed industrial scale: 270M attempts and $83.8M in losses, with $9.4M drained from 15 Tron holders in one campaign this week** — https://en.coin-turk.com/15-crypto-investors-lose-9-4-million-to-tron-address-poisoning-scam/
  **What happened:** 15 crypto investors lost a combined $9.4 million in one Tron address-poisoning campaign using look-alike addresses; separately, Bofur Capital lost $2 million to a 0.0002-USDC dust-then-poison pattern following a withdrawal from the Compound lending protocol; industry research published this week tallied 270 million address-poisoning attempts across Ethereum and BNB Smart Chain over two years with at least $83.8 million in confirmed losses.
  **Why it matters:** Address poisoning is no longer opportunistic. The dust transfer is essentially free to send, the technique requires no wallet compromise, and the failure mode (copying an address from transaction history) is the single most common user behavior in self-custody. Every address you have ever received a transfer from is now a candidate poison target.
  **Reader implication:** Run a complete scan of the last 90 days of outgoing transactions for any unauthorized dust transfer. For any future transfer above a trivial amount, verify the complete recipient address character-by-character on your hardware wallet's screen before signing; never copy addresses from transaction history for outgoing transfers.
  **Tags:** address poisoning, wallet hygiene, approval abuse
  **Severity:** High
  **Confirming source:** https://cryptorank.io/news/feed/830a1-bofur-capital-address-poisoning-attack

- **Payward, the parent of Kraken, adopted Claude Mythos as AI-driven security — the first major exchange publicly disclosed at that defensive tier** — https://medium.com/coinmonks/2026-cryptos-most-hacked-year-and-the-ai-race-to-defend-it-9ff0a1a17dec
  **What happened:** Payward, the parent company of Kraken, joined Project Glasswing and adopted Claude Mythos for security operations, becoming one of the first crypto firms publicly disclosed at this defensive tier; coverage framed the move against a year-to-date total of more than $1.2 billion stolen across 164 incidents, the worst year on record.
  **Why it matters:** Defensive AI has crossed from research to production at a major exchange. Expect custody providers and self-custody vendors to follow within 90 days; the gap between firms with AI-tier monitoring on withdrawal patterns and approval flows and those without will become a material due-diligence criterion for any institutional allocator or cautious individual.
  **Reader implication:** If you custody with an exchange or hosted wallet service, ask whether they have deployed AI-tier anomaly detection on withdrawal patterns, address-poisoning detection, and approval-flow monitoring. If they cannot answer, treat that as a material counterparty risk; if you self-custody, audit every approval on every wallet and revoke anything older than 30 days.
  **Tags:** infrastructure concentration, operational security, market structure
  **Severity:** Structural

- **An AI offensive-tool firm found a Ledger Ethereum app bug that lets a malicious dApp swap the APDU command during approval** — https://cryptorank.io/news/feed/74aa9-ledger-ethereum-app-bug-disclosure-clash
  **What happened:** TestMachine, an AI offensive-tool firm, identified a Ledger Ethereum app bug that allows a malicious dApp to swap the APDU command during the approval flow so users unknowingly sign unlimited token approvals; Ledger's CTO publicly framed the disclosure as fear-mongering and shipped a quiet fix; Chainalysis has linked the underlying vector to a broader pattern of approval-flow swaps seen in production drains.
  **Why it matters:** The bug exists at exactly the layer hardware wallets are supposed to defend. A user who reads their hardware wallet's screen and approves an "Approve USDC" prompt can be signing something materially different because the command was swapped mid-flow. The CTO's dismissive response also signals how the AI-to-vendor disclosure pipeline will need to mature as offensive tooling accelerates.
  **Reader implication:** For any approval above trivial amounts, verify the full contract address and method on your hardware wallet's screen, not just the token and amount. If your Ledger wallet has not been updated since the disclosure, update firmware immediately and audit recent approvals for unlimited allowances you did not intend to grant.
  **Tags:** approval abuse, firmware risk, operational security
  **Severity:** High

- **Boltz shut down its Bitcoin bridge after AI-assisted hacks outpaced its small team's defenses** — https://shattered.io/boltz-bitcoin-bridge-ai-hack-shutdown-2026/
  **What happened:** Boltz shut down its Bitcoin swap bridge on August 3, 2026 after AI-assisted hacks outpaced its small team's defensive capacity; the founders exited the project 10 days later. Coverage framed the shutdown as the first case of a small-team bridge operator conceding the AI offensive-defensive imbalance, with the implication that the gap between small-team and institutional-tier bridge operators has become unbridgeable.
  **Why it matters:** A small-team bridge cannot match the pace of AI-assisted offensive tooling. This is the operational signal for the entire bridge category: the defensive bar has moved, the teams that cannot clear it will exit, and the survivors will consolidate. Holders using bridges should expect consolidation and a higher operational premium on bridge fees.
  **Reader implication:** If you use any bridge to move funds between chains, audit the team's defensive posture: do they have AI-tier monitoring, do they publish incident reports, do they use multisig with enforced timelocks on upgrades and treasury movements? If not, treat that bridge as a material counterparty risk and consolidate to one with a published defensive posture.
  **Tags:** bridge exploit, infrastructure concentration, operational security
  **Severity:** Structural


### Items (raw, archived for completeness)
- **Maya Protocol Hack Drains $1.7M, CACAO Crashes 88.7%** — https://shattered.io/maya-protocol-hack-cacao-crash-2026/
  > Flash loan exploit on Maya Protocol with an 88.7% native-token crash; small absolute loss but large relative-impact for protocol users.
  *Editorial disposition: Folded into the address-poisoning Key development as a counterpoint on DeFi protocol failure modes.*

- **Address Poisoning: $2M Lost Over 7 of 40 Characters** — https://cryptoticker.io/en/address-poisoning-check-wallet-address/
  > Deep dive on the Bofur Capital incident; seven of forty characters matching is enough to defeat most users' verification habits.
  *Editorial disposition: Confirming source for the address-poisoning Key development.*

- **Term Labs Loses $8.5M in Governance Exploit** — https://finance.yahoo.com/markets/crypto/articles/another-defi-hack-term-labs-123536364.html
  > Governance attack funded by Tornado Cash; another in the year's $1.2B+ DeFi loss total.
  *Editorial disposition: Below the editorial bar as a standalone development — folded into the signal as part of the broader DeFi governance-failure pattern documented by Metaverse Post's August 2026 exploit wave piece.*

- **Bofur Capital loses $2M in address poisoning attack after Compound withdrawal** — https://cryptorank.io/news/feed/830a1-bofur-capital-address-poisoning-attack
  > Same Bofur Capital incident as Cryptoticker, with the Compound-withdrawal trigger detail.
  *Editorial disposition: Confirming source for the address-poisoning Key development.*

- **Stablecoin Depeg Risk: Historical Cases, Warning Signs, and Recovery Paths** — https://pro.edgex.exchange/en-US/news/article/stablecoin-depeg-history-ust-usdc-usdt-fdusd
  > Reference catalog of historical depegs with structural categorization.
  *Editorial disposition: Folded into the why-it-matters bullet on stablecoin exposure concentration.*

- **Can You Insure Stablecoins Against a Depeg?** — https://stablecoininsider.org/stablecoin-depeg-insurance/
  > Practical reference on third-party depeg-insurance products and the underlying counterparty risk they transfer rather than eliminate.
  *Editorial disposition: Folded into the what-to-do-this-week bullet on stablecoin exposure audit.*

- **Stablecoin Depegs Explained: What Really Happens When a Digital Dollar Breaks the Buck** — https://news.bitcoin.com/learning-insights/stablecoin-depegs-explained/
  > Mechanics explainer with category-level market-cap data for 2026.
  *Editorial disposition: Below the editorial bar as a standalone development — used as background context for the structural signal on stablecoin risk.*

- **You Approved a Wallet Signature. The Theft Comes Later** — https://www.secureworld.io/industry-news/crypto-wallet-signature-theft
  > Vocabulary-level explainer distinguishing Permit2 signatures from standard approvals.
  *Editorial disposition: Below the editorial bar as a standalone development — folded into the approval-abuse and revoke-your-approvals guidance.*

- **GoCaracal Malware Uses Ethereum Smart Contract to Fetch Replacement C2 Address** — https://thehackernews.com/2026/08/gocaracal-malware-uses-ethereum-smart.html
  > Malware variant uses an Ethereum smart contract to update its command-and-control endpoint without shipping a new binary.
  *Editorial disposition: Below the editorial bar as a standalone development — folded into the AI-on-both-sides signal as evidence that offensive infrastructure is also going on-chain.*

- **How Scammers Are Draining Crypto Wallets In 2026 Without Ever Asking For Your Seed Phrase** — https://themerkle.com/how-scammers-are-draining-crypto-wallets-in-2026-without-ever-asking-for-your-seed-phrase
  > Overview of turnkey wallet-drainer kits sold to less technical scammers.
  *Editorial disposition: Folded into the AI-on-both-sides signal paragraph as the canonical drainer-kit reference.*

- **Wallet Drainers: What You Really Approve on Confirm** — https://cryptoticker.io/en/wallet-drainer-token-approval-signature/
  > Mechanistic walkthrough of the approval flow that drainer kits exploit.
  *Editorial disposition: Folded into the approval-abuse and revoke-your-approvals guidance.*

- **Most secure crypto wallets in 2026 (MetaMask)** — https://metamask.io/news/most-secure-crypto-wallets
  > Vendor-positioned explainer with security-feature checklist.
  *Editorial disposition: Below the editorial bar — vendor explainer, not a development.*

- **Crypto self-custody security: your 2026 checklist guide (Diamond Pigs)** — https://www.diamondpigs.com/blog/crypto-self-custody-security-checklist-2026
  > Generic self-custody checklist; below the editorial bar.
  *Editorial disposition: Dropped from Key developments — generic checklist, not a development.*

- **Coldcard Enhances Seed Generation and Coinkite Warns Existing Phrases Remain Unsafe** — https://crypto-economy.com/coldcard-enhances-seed-generation-and-coinkite-warns-existing-phrases-remain-unsafe/
  > Crypto Economy's coverage of the Coinkite firmware update with the same 1,778-BTC loss figure.
  *Editorial disposition: Confirming source for the Coldcard Key development.*

- **What is Etherscan? How to use the Ethereum explorer** — https://crypto.news/what-is-etherscan-ethereum-blockchain-explorer/
  > Generic Etherscan explainer with embedded approval-revocation pointer.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*

- **Crypto Scams 2026: Common Types and How to Spot Them (Diamond Pigs)** — https://www.diamondpigs.com/blog/crypto-scams-2026
  > Generic consumer-protection guide on AI-generated scams; no new development.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*

- **Crypto Scams September 2026: The Complete Active Threats List** — https://www.coingabbar.com/en/crypto-blogs-details/crypto-scam-alert-list-active-fraud-schemes-2026
  > Monthly threat-list roundup echoing the week's primary stories.
  *Editorial disposition: Below the editorial bar as a standalone development — confirmed-signal echo, not a primary item.*

- **Crypto Phishing in 2026: Risks & How to Manage Them** — https://www.chainupad.com/blog/what-is-phishing-in-crypto/
  > Generic phishing primer; confirms the 270M address-poisoning figure.
  *Editorial disposition: Below the editorial bar — generic explainer; the 270M figure folded into the address-poisoning Key development.*

- **What Is a Stablecoin Depeg? Causes and Real Examples (Bitsgap)** — https://bitsgap.com/blog/what-is-a-stablecoin-depeg
  > Generic stablecoin depeg explainer with 2022–2026 examples.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*

- **Dust Attack and Address Poisoning (DailyCoin)** — https://dailycoin.com/dust-attack-and-address-poisoning-the-tiny-transactions-that-could-cost-you-a-lot
  > Generic dust-attack explainer.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*

- **CyberLeek Crypto Explained: GTA 6 Links, Risks, Price Hype & Red Flags** — https://www.bleap.finance/en-us/blog/cyberleek-crypto-gta-6-token
  > CyberLeek / GTA 6 leak-coin summary; same incident as Polygon and IGN pieces.
  *Editorial disposition: Below the editorial bar — confirms the GTA 6 leak-coin attribution trail but adds no new development.*

- **GTA 6 Leaks Increasingly Seem To Be Just A Big Crypto Scam (Kotaku)** — https://kotaku.com/gta-6-leaks-crypto-scam-2000726671
  > GTA 6 / CyberLeek coverage with the KuCoin-wallet attribution trail.
  *Editorial disposition: Below the editorial bar — confirms the paper-trail-to-KYC-exchange lesson without adding a primary development.*

- **August 2026's Exploit Wave: Governance Failures, Protocol Bugs, And A Widening Attack Surface (Metaverse Post)** — https://mpost.io/august-2026s-exploit-wave-governance-failures-protocol-bugs-and-a-widening-attack-surface/
  > Monthly exploit-wave roundup; flags the $30M H1 2026 physical-coercion figure (37% home invasions).
  *Editorial disposition: Folded into the AI-on-both-sides signal as the canonical monthly-wave context.*

- **Stablecoin Yield Strategies: Low-Risk to High (Eco)** — https://eco.com/support/en/articles/13313563-stablecoin-yield-strategies-low-risk-to-high
  > Stablecoin-yield tier catalog with 4.1–11.8% range.
  *Editorial disposition: Below the editorial bar — generic yield-strategy catalog, not a development.*

- **What Is an EOA? Externally Owned Accounts (Eco)** — https://eco.com/support/en/articles/12005956-what-is-an-eoa-externally-owned-accounts
  > Generic EOA explainer.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*

- **2026 Crypto's Most-Hacked Year, and the AI Race to Defend It (Coinmonks)** — https://medium.com/coinmonks/2026-cryptos-most-hacked-year-and-the-ai-race-to-defend-it-9ff0a1a17dec
  > Year-to-date hack tally with the Payward / Claude Mythos adoption detail.
  *Editorial disposition: Primary source for the AI-defenders Key development.*

- **Stablecoin Competition Moves From Issuing Tokens to Owning Distribution (PYMNTS)** — https://www.pymnts.com/cryptocurrency/2026/stablecoin-competition-moves-from-issuing-tokens-to-owning-distribution/
  > Structural piece on stablecoin distribution-channel competition.
  *Editorial disposition: Below the editorial bar — structural explainer, not a primary development for this week.*

- **Cumberland Stablecoin Commentary: August 16** — https://www.cumberland.io/insights/commentary/cumberland-stablecoin-commentary-august-16-2026
  > Trading-desk note that current drawdowns are not depegs by any reasonable definition.
  *Editorial disposition: Folded into the stablecoin-concentration bullet as counter-evidence on the no-depeg-but-tight-spread baseline.*

- **When Stablecoins Lose Their $1 Peg: Causes and Risks** — https://www.gncrypto.news/news/when-stablecoins-lose-their-1-peg/
  > Generic depeg explainer.
  *Editorial disposition: Below the editorial bar — generic explainer, not a development.*


### Related reading
- **Seed Phrases: What They Are and How People Lose Them** — /guides/seed-phrases-what-they-are-and-how-people-lose-them/
- **How to Verify a Hardware Wallet Before You Use It** — /guides/verify-hardware-wallet/
- **Address Poisoning: The Quiet Cousin of Approval Abuse** — /guides/address-poisoning/
- **The Wallet Safety Checklist** — /tools/wallet-safety-checklist/
