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
      <Challenge />
      <Ledger />
      <Footer />
    </>
  );
}
