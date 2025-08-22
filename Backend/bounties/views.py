from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from datetime import datetime, timezone
from django.db.models import Q

from user.models import MyUser
from user.serializers import BountyFreelancerSerializer
from .models import (
    Bounties,
    BountyFreelancerMap,
    Chat_table,
    Request_table,
    Dispute_messages_table,
    Voting_table,
)
from .serializers import (
    AcceptBountySerializer,
    GetBountySerializer,
    RequestBountySerializer,
    BountySerializer,
    CreateBountySerializer,
    MessageSerializer,
    ComplaintSerializer,
    voteBountySerializer,
)

from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta


@api_view(["GET"])
def bounty_types(request):
    task_types = Bounties.objects.values_list("task_type", flat=True).distinct()

    sort_by = request.GET.get("sort_by", "task_type")
    ordering = []
    if sort_by:
        ordering = [field.strip() for field in sort_by.split(",")]
    if ordering:
        task_types = task_types.order_by(*ordering)

    return Response({"task_types": task_types}, status.HTTP_200_OK)


@api_view(["GET"])
def get_bounties(request, task_type_value):
    data = request.data
    task_bounties = Bounties.objects.filter(task_type=task_type_value).filter(
        is_assigened=False
    )

    sort_by = request.GET.get("sort_by", "title")
    ordering = []
    if sort_by:
        ordering = [field.strip() for field in sort_by.split(",")]
    if ordering:
        task_bounties = task_bounties.order_by(*ordering)

    serializer = GetBountySerializer(instance=task_bounties, many=True)
    return Response({"bounties": serializer.data}, status.HTTP_200_OK)


@api_view(["POST"])
def request_bounty(request):
    data = request.data
    serializer = RequestBountySerializer(data=data)

    if not serializer.is_valid():
        return Response(
            {"status": False, "message": serializer.errors}, status.HTTP_400_BAD_REQUEST
        )

    serializer.save()

    return Response(
        {"status": True, "message": "Bounty Requested"}, status.HTTP_201_CREATED
    )


@api_view(["GET"])
def get_freelancer_bounties(request, freelancer_id, bounty_type):

    if not MyUser.objects.filter(is_client=False).filter(id=freelancer_id).exists():
        return Response(
            {"status": False, "message": "Invalid Freelancer ID"},
            status.HTTP_400_BAD_REQUEST,
        )

    freelancer_bounty_ids = BountyFreelancerMap.objects.filter(
        assigned_candidate_id=freelancer_id
    ).values_list("bounty_id", flat=True)
    freelancer_bounties = Bounties.objects.filter(id__in=freelancer_bounty_ids)

    if bounty_type == "INPROGRESS":
        freelancer_bounties = freelancer_bounties.filter(is_completed=False)
    elif bounty_type == "COMPLETED":
        freelancer_bounties = freelancer_bounties.filter(is_completed=True).filter(
            is_amount_transfered=False
        )
    elif bounty_type == "PAID":
        freelancer_bounties = freelancer_bounties.filter(is_completed=True).filter(
            is_amount_transfered=True
        )

    sort_by = request.GET.get("sort_by", "title")
    ordering = []
    if sort_by:
        ordering = [field.strip() for field in sort_by.split(",")]
    if ordering:
        freelancer_bounties = freelancer_bounties.order_by(*ordering)

    serializer = BountySerializer(instance=freelancer_bounties, many=True)

    return Response({"freelancer_bounties": serializer.data}, status.HTTP_200_OK)


class Bounty(APIView):

    def post(self, request):
        data = request.data
        serializer = CreateBountySerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {"status": False, "message": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {
                "status": True,
                "message": "Bounty Created Successfullly",
            },
            status.HTTP_201_CREATED,
        )


@api_view(["GET"])
def get_client_bounties(request, client_id, bounty_type):

    client_bounties = Bounties.objects.filter(client_id=client_id)
    if bounty_type == "INPROGRESS":
        client_bounties = client_bounties.filter(is_completed=False)
    elif bounty_type == "COMPLETED":
        client_bounties = client_bounties.filter(is_completed=True).filter(
            Q(is_amount_transfered=False) | Q(is_client_amount_transfered=False)
        )
    elif bounty_type == "PAID":
        client_bounties = client_bounties.filter(is_completed=True).filter(
            is_amount_transfered=True
        )

    sort_by = request.GET.get("sort_by", "-id")
    ordering = []
    if sort_by:
        ordering = [field.strip() for field in sort_by.split(",")]
    if ordering:
        client_bounties = client_bounties.order_by(*ordering)

    serializer = BountySerializer(instance=client_bounties, many=True)
    if bounty_type == "COMPLETED" or bounty_type == "PAID":
        return Response({"client_bounties": serializer.data}, status.HTTP_200_OK)
    else:
        client_bounties = serializer.data
        for bounty in client_bounties:
            if Request_table.objects.filter(bounty_id=bounty["id"]).exists():
                bounty["is_requested"] = True
            else:
                bounty["is_requested"] = False
        return Response({"client_bounties": client_bounties}, status.HTTP_200_OK)


@api_view(["GET"])
def submit_bounty(request, bounty_id):
    bounty = Bounties.objects.get(id=bounty_id)
    bounty.is_completed = True
    bounty.save()

    return Response(
        {"status": True, "message": " Bounty Submitted Successfully"},
        status.HTTP_200_OK,
    )


@api_view(["GET"])
def transfer_directly_amount(request, bounty_id):
    bounty = Bounties.objects.get(id=bounty_id)
    bounty.is_amount_transfered = True
    bounty.is_client_amount_transfered = True
    bounty.save()

    user = BountyFreelancerMap.objects.get(bounty_id=bounty_id).assigned_candidate_id
    user.earned_task_reward += bounty.amount
    user.save()

    return Response(
        {"status": True, "message": " Amount Transfered Successfully "},
        status.HTTP_200_OK,
    )


@api_view(["GET"])
def get_bounties_request(request, bounty_id):

    if not Bounties.objects.filter(id=bounty_id).exists():
        return Response(
            {"status": False, "message": "Invalid Bounty ID"},
            status.HTTP_400_BAD_REQUEST,
        )

    bounties_requests = Request_table.objects.filter(bounty_id=bounty_id)
    freelancer_address_map = {
        req.requested_candidate_id.id: req.candidate_pera_wallet_address
        for req in bounties_requests
    }
    bounty_request_ids = freelancer_address_map.keys()
    freelancer_details = MyUser.objects.filter(id__in=bounty_request_ids)
    serializer = BountyFreelancerSerializer(instance=freelancer_details, many=True)

    data_with_wallets = []
    for user in serializer.data:
        user_id = user["id"]
        user["wallet_address"] = freelancer_address_map.get(user_id, "")
        data_with_wallets.append(user)

    return Response({"requested_candidates": data_with_wallets}, status.HTTP_200_OK)


class accept_bounty_request(APIView):

    def post(self, request):
        data = request.data
        serializer = AcceptBountySerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {"status": False, "message": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        # delete all the pending requested ID's
        Request_table.objects.filter(bounty_id=data["bounty_id"]).delete()

        bounty = Bounties.objects.get(id=data["bounty_id"])

        bounty.is_assigened = True
        # Set end_date using months instead of days
        bounty.start_date = date.today()
        bounty.end_date = date.today() + relativedelta(months=bounty.deadline)
        bounty.save()

        return Response(
            {
                "status": True,
                "message": "Bounty Accepted Successfullly",
            },
            status.HTTP_201_CREATED,
        )


class message(APIView):
    def post(self, request):
        data = request.data
        serializer = MessageSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {"status": False, "message": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {"status": True, "message": "Message sent successfully"},
            status.HTTP_201_CREATED,
        )

    def get(self, request, bounty_id):
        if not bounty_id:
            return Response(
                {"status": False, "message": "Bounty_id is Required"},
                status.HTTP_400_BAD_REQUEST,
            )
        bounty = Bounties.objects.get(id=bounty_id)
        client_id = bounty.client_id.id

        message = Chat_table.objects.filter(bounty_id=bounty_id).order_by("id")
        serializers = MessageSerializer(message, many=True)
        user_ids = set([msg["user"] for msg in serializers.data])
        users = MyUser.objects.filter(id__in=user_ids)
        user_map = {user.id: user.username for user in users}

        enriched_messages = []
        for msg in serializers.data:
            msg["username"] = user_map.get(msg["user"], "Unknown")
            msg["isClient"] = msg["user"] == client_id
            enriched_messages.append(msg)

        return Response({"status": True, "chat": enriched_messages}, status.HTTP_200_OK)


class Complaint_chat(APIView):
    def post(self, request):
        data = request.data
        serializer = ComplaintSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {"status": False, "message": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {"status": True, "message": "Complaint saved successfully"},
            status.HTTP_201_CREATED,
        )

    def get(self, request, bounty_id):
        if not bounty_id:
            return Response(
                {"status": False, "message": "Bounty_id is Required"},
                status.HTTP_400_BAD_REQUEST,
            )
        bounty = Bounties.objects.get(id=bounty_id)
        client_id = bounty.client_id.id

        message = Dispute_messages_table.objects.filter(bounty_id=bounty_id).order_by(
            "id"
        )
        serializers = ComplaintSerializer(message, many=True)
        user_ids = set([msg["user"] for msg in serializers.data])
        users = MyUser.objects.filter(id__in=user_ids)
        user_map = {user.id: user.username for user in users}

        enriched_messages = []
        for msg in serializers.data:
            msg["username"] = user_map.get(msg["user"], "Unknown")
            msg["isClient"] = msg["user"] == client_id
            enriched_messages.append(msg)

        return Response(
            {"status": True, "complaint": enriched_messages}, status.HTTP_200_OK
        )


@api_view(["GET"])
def get_bounties_details(request, bounty_id, freelancer_id):
    bounty = Bounties.objects.get(id=bounty_id)
    serializer = BountySerializer(bounty, many=False)
    is_bounty_requested = (
        Request_table.objects.filter(bounty_id=bounty_id)
        .filter(requested_candidate_id=freelancer_id)
        .exists()
    )
    client_name = bounty.client_id.username
    freelancer_name = None
    if bounty.is_assigened:
        freelancer_name = BountyFreelancerMap.objects.get(
            bounty_id=bounty_id
        ).assigned_candidate_id.username

    bounty_map = BountyFreelancerMap.objects.filter(bounty_id=bounty_id).first()
    assigned_candidate_id = bounty_map.assigned_candidate_id.id if bounty_map else None

    vote = (
        Voting_table.objects.filter(bounty_id=bounty_id)
        .filter(user=freelancer_id)
        .first()
    )
    voted_for = vote.voted_for if vote else None
    vote_active = vote.active if vote else None
    bounty_details = {
        **serializer.data,
        "is_bounty_requested": is_bounty_requested,
        "assigned_candidate_id": assigned_candidate_id,
        "voted_for": voted_for,
        "vote_active": vote_active,
        "client_name": client_name,
        "freelancer_name": freelancer_name,
    }
    if (
        bounty.is_disputed
        and bounty.dispute_end_date
        and datetime.now(timezone.utc) > bounty.dispute_end_date
    ):

        votes = Voting_table.objects.filter(bounty_id=bounty_id)
        freelancer_votes = votes.filter(voted_for="FREELANCER").count()
        client_votes = votes.filter(voted_for="CLIENT").count()

        if freelancer_votes > client_votes:
            winner = "FREELANCER"
        elif client_votes > freelancer_votes:
            winner = "CLIENT"
        else:
            winner = "TIE"
        bounty_details = {
            **bounty_details,
            "dispute_result": {
                "freelancer_votes": freelancer_votes,
                "client_votes": client_votes,
                "winner": winner,
            },
        }
    return Response(
        {"status": True, "bounty_details": bounty_details}, status.HTTP_200_OK
    )


@api_view(["POST"])
def accept_submission_link(request, bounty_id):
    data = request.data
    bounty = Bounties.objects.get(id=bounty_id)
    bounty.final_submission_link = data["finalSubmissionLink"]
    bounty.is_completed = True
    bounty.save()
    return Response(
        {
            "status": True,
            "message": "Final Submission Link Accepted Successfullly",
        },
        status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def voting(request):
    data = request.data
    serializer = voteBountySerializer(data=data)

    if not serializer.is_valid():
        return Response(
            {"status": False, "message": serializer.errors},
            status.HTTP_400_BAD_REQUEST,
        )

    serializer.save()
    return Response(
        {
            "status": True,
            "message": "Vote Submitted Successfullly",
        },
        status.HTTP_201_CREATED,
    )


@api_view(["DELETE"])
def delete_vote(request, bounty_id, user_id):
    vote = Voting_table.objects.get(Q(bounty_id=bounty_id) & Q(user=user_id))
    vote.active = False
    vote.save()

    votes_count = Voting_table.objects.filter(bounty_id=bounty_id).count()
    reward = Bounties.objects.get(id=bounty_id).amount
    user = MyUser.objects.get(id=user_id)
    user.earned_task_reward += (reward * 0.1) / votes_count
    user.save()

    return Response(
        {
            "status": True,
            "message": "Vote Deleted Successfullly",
        },
        status.HTTP_200_OK,
    )


@api_view(["GET"])
def get_reward_bounties(request, user_id):
    bounty_ids = (
        Voting_table.objects.filter(user_id=user_id)
        .filter(active=True)
        .values_list("bounty_id", flat=True)
    )
    bounties = Bounties.objects.filter(id__in=bounty_ids)

    serializer = BountySerializer(bounties, many=True)

    return Response(
        {
            "status": True,
            "reward_bounties": serializer.data,
        },
        status.HTTP_200_OK,
    )


@api_view(["GET"])
def transfer_amount(request, is_freelancer, bounty_id):
    bounty = Bounties.objects.get(id=bounty_id)
    is_freelancer = is_freelancer.lower() == "true"

    votes = Voting_table.objects.filter(bounty_id=bounty_id)
    freelancer_votes = votes.filter(voted_for="FREELANCER").count()
    client_votes = votes.filter(voted_for="CLIENT").count()

    if freelancer_votes > client_votes:
        winner = "FREELANCER"
    elif client_votes > freelancer_votes:
        winner = "CLIENT"
    else:
        winner = "TIE"
    num_of_voters = votes.count()

    if is_freelancer:
        bounty.is_amount_transfered = True
        if winner == "TIE":
            if num_of_voters == 0:
                reward = bounty.amount * 0.5
            else:
                reward = bounty.amount * 0.45
        else:
            bounty.is_client_amount_transfered = True
            if num_of_voters == 0:
                reward = bounty.amount
            else:
                reward = bounty.amount * 0.9
        user = BountyFreelancerMap.objects.get(
            bounty_id=bounty_id
        ).assigned_candidate_id
        user.earned_task_reward += reward
        user.save()

    else:
        bounty.is_client_amount_transfered = True
        if winner == "TIE":
            if num_of_voters == 0:
                reward = bounty.amount * 0.5
            else:
                reward = bounty.amount * 0.45
        else:
            bounty.is_amount_transfered = True
            if num_of_voters == 0:
                reward = bounty.amount
            else:
                reward = bounty.amount * 0.9
        user = bounty.client_id
        user.earned_task_reward += reward
        user.save()

    if (
        bounty.is_disputed
        and bounty.is_amount_transfered
        and bounty.is_client_amount_transfered
        and bounty.dispute_end_date < datetime.now(timezone.utc)
    ):
        bounty.is_disputed = False

    bounty.save()
    return Response(
        {
            "status": True,
            "message": "Paid Successfullly",
        },
        status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def raise_bounty_dispute(request, bounty_id):
    bounty = Bounties.objects.get(id=bounty_id)
    bounty.is_disputed = True
    bounty.dispute_end_date = (datetime.now() + timedelta(days=3)).isoformat()
    bounty.save()
    return Response(
        {
            "status": True,
            "message": "Dispute Raised Successfullly",
        },
        status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def get_disputed_bounties(request, user_id):
    bounty_ids = Voting_table.objects.filter(user_id=user_id).values_list(
        "bounty_id", flat=True
    )
    current_time = datetime.now(timezone.utc)
    disputed_bounties = (
        Bounties.objects.filter(is_disputed=True, dispute_end_date__gt=current_time)
        .exclude(client_id=user_id)
        .exclude(bountyfreelancermap__assigned_candidate_id=user_id)
        .exclude(id__in=bounty_ids)
        .distinct()
    )

    serializer = BountySerializer(disputed_bounties, many=True)

    return Response(
        {
            "status": True,
            "disputed_bounties": serializer.data,
        },
        status.HTTP_200_OK,
    )


@api_view(["GET"])
def get_freelancer_requested_bounties(request, freelancer_id):
    requested_bounty_ids = Request_table.objects.filter(
        requested_candidate_id=freelancer_id
    ).values_list("bounty_id", flat=True)
    requested_bounties = Bounties.objects.filter(id__in=requested_bounty_ids)
    serializer = BountySerializer(instance=requested_bounties, many=True)
    return Response(
        {
            "status": True,
            "requestedBounties": serializer.data,
        },
        status.HTTP_200_OK,
    )
