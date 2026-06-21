export const metadata = {
  title: "BTC direction predictor",
  description: "Educational BTC direction prediction dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}
