import { Link } from "react-router";
import { PageHeader } from "../components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader title="This page doesn't exist" lede="The link may be out of date. Start from the overview, or pick a section from the navigation." />
      <Link className="btn" to="/">Go to the overview</Link>
    </>
  );
}
