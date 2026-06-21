# BTC Direction Predictor — Full Automated Website

Ye project 3 cheezein automatically karta hai:
1. **GitHub Actions** har ghante BTC data fetch karta hai, model train karta hai,
   aur naya prediction `prediction.json` me save karta hai
2. **Website** (Next.js) ye prediction file padhke dikhata hai, saath me live price
3. Sab kuch **free** hai — GitHub aur Vercel ke free tier pe chalega

## ⚠️ Data source update (zaroor padhein)

Pehle ye pipeline Binance API use kar raha tha, lekin **Binance kuch regions ko
geo-block karta hai (HTTP 451 error)** — jisme GitHub Actions ke servers bhi
shamil hain. Isliye ab pipeline **CoinGecko ka free public API** use karta hai,
jo geo-block nahi karta.

Trade-off: CoinGecko free plan exact exchange-style OHLC candles nahi deta
(sirf price points), aur history ki lambai ke hisaab se granularity automatic
badalti hai (chota history window = fine-grained jaise ~15min, lamba window =
coarser jaise hourly). Isliye `predict_and_save.py` khud-ba-khud sabse achi
available granularity choose karta hai jisme kaafi history mile (kam se kam
~400 candles). Final JSON me `"interval"` field se pata chal jaata hai
actual me kaunsa interval use hua — ye hamesha "15m" nahi hoga, kabhi "60m"
(1 hour) bhi ho sakta hai. Website is field ko display karke sahi context deti hai.

## Project structure

```
btc-web-project/
├── .github/workflows/update_prediction.yml   <- automation (har ghante chalta hai)
├── pipeline/
│   ├── data_fetch.py        <- CoinGecko se data laata hai
│   ├── features.py          <- technical indicators banata hai
│   ├── predict_and_save.py  <- model train karta hai, prediction.json banata hai
│   └── requirements.txt
└── website/
    ├── app/page.js           <- dashboard UI
    ├── app/layout.js
    ├── public/prediction.json  <- yahaan latest prediction save hoti hai
    └── package.json
```


---

## Step-by-step setup (beginner ke liye)

### Step 1 — GitHub pe repo banao

1. github.com pe login karo
2. "New repository" pe click karo, naam do jaise `btc-direction-predictor`
3. **Public** rakho (private bhi chalega, par GitHub Actions free minutes thode kam milte hain)
4. "Create repository" pe click karo

### Step 2 — Apna code GitHub pe upload karo

Apne computer pe terminal/command-prompt khol ke, jis folder me ye saari files hain
wahaan jaake ye commands chalao (`YOUR-USERNAME` aur `YOUR-REPO-NAME` apne se replace karo):

```bash
git init
git add .
git commit -m "Initial commit - BTC predictor"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git push -u origin main
```

Agar `git` command nahi chal rahi, [git-scm.com](https://git-scm.com) se install karo pehle.

### Step 3 — GitHub Actions ko enable/test karo

1. GitHub pe apni repo khol kar **"Actions"** tab pe jao
2. Tumhe "BTC Prediction Update" workflow dikhega
3. Usse pehli baar **manually** chalane ke liye: workflow pe click karo →
   "Run workflow" button dabao
4. 1-2 minute me ye chal jaayega aur `website/public/prediction.json` automatically
   update ho jaayegi (ek naya commit dikhega repo me)
5. Iske baad ye **automatic** har ghante khud chalega — tumhe kuch nahi karna

Agar workflow fail ho jaaye, "Actions" tab me uske logs dekh ke error samajh sakte ho —
zyada tar dependency install ya API rate-limit ka issue hota hai.

### Step 4 — Vercel pe website deploy karo

1. [vercel.com](https://vercel.com) pe jao, "Sign up" karo — GitHub account se
   login karna sabse easy hai
2. "Add New Project" pe click karo
3. Apni GitHub repo select karo (jo Step 1 me banayi thi)
4. **IMPORTANT**: "Root Directory" field me `website` likho (kyunki Next.js app
   `website` folder ke andar hai, repo ke root me nahi)
5. "Deploy" pe click karo
6. 1-2 minute me website live ho jaayegi, ek URL milega jaise
   `your-project.vercel.app`

### Step 5 — Check karo sab kaam kar raha hai

1. Apni Vercel URL kholo — dashboard dikhna chahiye prediction ke saath
2. Agar prediction purani lag rahi hai, GitHub Actions tab me check karo
   ki workflow successfully chal raha hai har ghante
3. Jab bhi GitHub Actions naya commit karta hai `prediction.json` me,
   Vercel **automatically redeploy** kar dega (ye built-in feature hai) —
   tumhe kuch manually karne ki zaroorat nahi

---

## Important honest baat

Walk-forward accuracy jo dikhegi wo zyada tar 50% ke aas-paas hi rahegi —
ye coin-flip jaisa hai. Ye project ML pipeline aur automation seekhne/dikhane
ke liye bahut accha hai, lekin **isse real money trade na karein** bina
bahut zyada deeper testing ke.

## Aage kya improve kar sakte ho

- Har candle ke baad actual result vs prediction track karke ek "accuracy over time"
  chart bana sakte ho (isके liye database chahiye hoga, jaise Supabase free tier)
- Telegram/Discord bot bana sakte ho jo naya prediction aate hi message bheje
  (GitHub Actions workflow me ek extra step add karna hoga)
- Multiple timeframes (1h, 4h) ke predictions ek saath dikha sakte ho
