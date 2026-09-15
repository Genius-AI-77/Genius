import { Nav, Stage, Ticker } from "./components/Chrome";
import {
  Agents,
  Challenge,
  Desk,
  Hero,
  Machine,
  Method,
  Connect,
  Veto,
} from "./components/Sections";
import { Footer, Ledger } from "./components/Ledger";
import { TokenSection } from "./components/TokenCA";

export default function App() {
  return (
    <>
      <Stage />
      <Nav />
      <Ticker />
      <Hero />
      <Machine />
      <Agents />
      <Method />
      <Veto />
      <Desk />
      <Connect />
      <TokenSection />
      <Challenge />
      <Ledger />
      <Footer />
    </>
  );
}
