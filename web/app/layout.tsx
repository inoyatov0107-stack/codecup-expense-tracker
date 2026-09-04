import "./style.css";
export const metadata = { title: "Мои расходы", description: "Трекер расходов в Telegram" };
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="ru"><body>{children}</body></html>; }
