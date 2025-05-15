#### EIP-7002: Enhancing Staking Liquidity via Execution Layer-Controlled Exits

##### Intro 

With **EIP-7002**, Ethereum introduces Execution Layer (EL) control over validator exits. This proposal allows stakers to initiate validator withdrawals directly via EL transactions, unlocking new flexibility in managing staked assets. But with this flexibility comes complexity — particularly around queue mechanics, churn limits, and dynamic fees. Understanding these elements is critical to optimizing liquidity strategies and operational efficiency.

##### Overview of Exit Types Under EIP-7002

EIP-7002 enables validators to submit a withdrawal\_request via the EL, which can be either:

* Full Exit:  
  * Withdraw the entire validator balance and cease validator duties.  
  * Triggered when amount \= 0\.  
* Partial Exit:  
  * Withdraw a portion of the validator’s balance, ensuring that at least 32 ETH remains so the validator can continue operating and performing its duties  
  * Triggered when amount \> 0\.

These requests, once submitted, follow distinct processing paths based on the type of exit.

##### Submission & Fee Mechanics

* Every withdrawal\_request requires a submission fee.  
* Key Points:  
  1. The fee is independent of the amount of ETH requested — whether you're withdrawing 1 ETH or 30 ETH, the fee logic remains the same.  
  2. Fees are deterministic at the time of submission.  
  3. The fee is dynamically calculated based on the number of excess withdrawal\_request:  
     * The “excess” is a metric tracked on-chain by the smart contract. It is calculated as: “excess” from the previous block \+ (\# of withdrawal\_request in the current block \- 2\)    
     * The “excess” updated every block, increasing or decreasing depending on the \# of withdrawal\_request in the previous block.  
     * Relative to Ethereum's target of 2 withdrawal requests per block.

Ethereum targets 2 withdrawal\_request per block. Any number above this target increases the fee:

| Excess withdrawal\_requests | Fee (ETH) |
| :---- | :---- |
| 627 | \~0.01 ETH |
| 654 | \~0.05 ETH |
| 666 | \~0.10 ETH |
| 681 | \~0.25 ETH |

This fee mechanism incentivizes users to submit requests during quieter periods, ensuring orderly exits.

##### The Churn Limit: Ethereum’s Exit Throttle

Ethereum enforces a churn limit to control how much stake can exit per epoch, preserving network security and stability:

* Churn Limit \= 256 ETH per epoch (applies across all exit types):  
  * EL Full Exits (EIP-7002 \- withdrawal\_request)  
  * EL Partial Exits (EIP-7002 \- withdrawal\_request)  
  * CL Full Exits (SignedVoluntaryExit)  
* This sets a maximum limit of 57,600 ETH (\~$115M assuming $2000 per ETH) that can become withdrawable each day.  
  * Additional Exit requests will be delayed to subsequent days.

**How It Works**

* The churn limit is consumed on a first-come, first-served basis.  
  * Whether an EL partial, EL full, or CL full exit — whichever request gets processed first will consume available churn capacity.  
* Ethereum tracks:  
  * earliest\_exit\_epoch: The earliest next epoch when exits can occur.  
  * exit\_balance\_to\_consume: Remaining ETH that can be processed within that epoch.

As exit requests are processed:

* If a request's amount fits within exit\_balance\_to\_consume:  
  * It is assigned to the current earliest\_exit\_epoch.  
* If it exceeds the available balance:  
  * The request is deferred, with earliest\_exit\_epoch incremented accordingly:  
    * exit\_epoch \= earliest\_exit\_epoch \+ (excess\_amount / 256 rounded up).  
* Once assigned an exit\_epoch, the withdrawable\_epoch is calculated as:  
  * withdrawable\_epoch \= exit\_epoch \+ 256 (This fixed delay ensures validators have fully exited and prevents rapid liquidity shifts.)  
* After a validator’s exit\_epoch elapses they are no longer required to perform its duties

The churn limit determines timing — but there’s no literal "queue" data structure for EL and CL Full Exits. Instead, the queue is virtual, defined by the assignment of exit\_epoch and withdrawable\_epoch values.

##### Exit Path Differences Explained

1. **EL Full Exits & CL Full Exits**  
   * Both types:  
     * Consume churn limit.  
     * Receive:  
       * An exit\_epoch — when validator duties officially end.  
       * A withdrawable\_epoch \= exit\_epoch \+ 256 — when ETH becomes claimable.  
   * These exits are purely governed by epoch assignments; there is no physical queue holding the requests.  
2. **EL Partial Exits**  
   * Partial exits behave differently:  
     * Consume churn limit.  
     * Validators continue performing duties — so they do not receive an exit\_epoch.  
     * Only a withdrawable\_epoch is assigned, based on churn limit consumption.  
   * Once processed, partial exits enter a real pending\_partial\_withdrawals queue.  
   * Dequeue Process  
     * A partial withdrawal becomes eligible when:  
       * current\_epoch \>= withdrawable\_epoch.  
     * However, Ethereum limits this to 8 partial withdrawals per block.  
     * If more than 8 are eligible, the remainder stays in the queue for future blocks.

##### How Exit Types Interact: The Liquidity Domino Effect

All three exit paths — EL full, CL full, and EL partial — compete for the same churn limit.

Key Implications:

* Heavy full exit activity (e.g., validators rotating out or reacting to market volatility) will:  
  * Consume churn capacity, delaying the processing of EL partial exits.  
  * Push back the assignment of withdrawable\_epoch for partial requests.  
* Even if a validator submits a timely partial exit:  
  * If there’s a surge in full exits across the network, the partial exit will inherit those delays.  
  * After reaching withdrawable\_epoch, further delays can occur due to the 8-per-block dequeue limit.

#### Notes

Potential estimation of churn limit consumption and impact on withdrawable\_epoch:

* there are currently an avg of 1300 validators exited per, each with 32 ETH  
* 1300 \* 32 \= 41,600 ETH exited a day  
* The max churn limit is 256 ETH per epoch which is 57,600 ETH per day  
* thus 41,600 / 57,600 or \~72% of the max churn limit is used per day  
* therefore the worst case earliest\_exit\_epoch on any given day could be 72% \* 24 hrs \= 17.33 hours

##### 1\. Ethereum Block Gas Limit

* Current mainnet block gas limit ≈ **36 million gas**.

* Hoodi testnet (Pectra) should have similar limits unless configured otherwise.

---

##### 2\. How Much Gas Does a `WithdrawalRequest` Cost?

This depends on:

* The system contract implementation.

* Storage writes (`sstore`), which are expensive (\~20,000 gas per slot written).

* Base transaction cost (21,000 gas minimum).

From typical precompile/system contract behavior, let's estimate:

| Operation | Gas Estimate |
| ----- | ----- |
| Base transaction cost | 21,000 |
| `sstore` for incrementing count | 20,000 |
| `sstore` x3 for queue storage (validator, amount, etc.) | 60,000 |
| Misc overhead (function logic, checks) | \~5,000 |
| **Total per `WithdrawalRequest` tx** | **\~106,000 gas** |

(This is a reasonable ballpark — could vary depending on optimizations.)

---

##### 3\. Max Requests Per Block

Now calculate:

python  
CopyEdit  
`Max_Requests_Per_Block = Block_Gas_Limit // Gas_Per_WithdrawalRequest`

Using:

* `36,000,000 // 106,000 ≈ 339 requests`

So **\~339 `WithdrawalRequest` txs** could theoretically fit in a fully packed block.

