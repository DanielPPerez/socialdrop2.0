export const metadata = {
  title: 'SocialDrop',
  description: 'Automate social media publishing',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}