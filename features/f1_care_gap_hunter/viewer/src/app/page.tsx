import { redirect } from "next/navigation";

// Chat is the default screen - see nav.tsx for the worklist switch.
export default function HomePage() {
  redirect("/chat");
}
